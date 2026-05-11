import requests
import time
import random
import string
from typing import Dict, List, Tuple

class RobloxUsernameChecker:
    """
    Checks Roblox username availability using official Roblox APIs.
    Uses the most reliable endpoint for accuracy.
    """
    
    # Roblox API endpoints
    BATCH_USERNAMES_URL = "https://users.roblox.com/v1/usernames/users"
    USERS_GET_BY_USERNAME_URL = "https://api.roblox.com/users/get-by-username"
    
    # Username validation rules
    USERNAME_MIN_LENGTH = 3
    USERNAME_MAX_LENGTH = 20
    
    def __init__(self, rate_limit_delay: float = 0.5):
        """
        Initialize the checker with rate limiting.
        
        Args:
            rate_limit_delay: Delay in seconds between requests (avoid rate limiting)
        """
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        })
    
    def _enforce_rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()
    
    def validate_format(self, username: str) -> Tuple[bool, str]:
        """
        Validate username format against Roblox rules.
        
        Args:
            username: Username to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not username:
            return False, "Username cannot be empty"
        
        if len(username) < self.USERNAME_MIN_LENGTH:
            return False, f"Username must be at least {self.USERNAME_MIN_LENGTH} characters"
        
        if len(username) > self.USERNAME_MAX_LENGTH:
            return False, f"Username must be at most {self.USERNAME_MAX_LENGTH} characters"
        
        # Check allowed characters (alphanumeric and underscore)
        if not all(c.isalnum() or c == '_' for c in username):
            return False, "Username can only contain letters, numbers, and underscores"
        
        # Can't start or end with underscore
        if username.startswith('_') or username.endswith('_'):
            return False, "Username cannot start or end with underscore"
        
        return True, ""
    
    def check_availability_batch(self, username: str) -> Dict:
        """
        Check availability using the batch users endpoint.
        This is the most reliable endpoint for accurate results.
        
        Args:
            username: Username to check
            
        Returns:
            Dictionary with availability info
        """
        self._enforce_rate_limit()
        
        try:
            response = self.session.post(
                self.BATCH_USERNAMES_URL,
                json={"usernames": [username]},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                data_list = data.get("data", [])
                
                # If we get back user data, username is taken
                if data_list and len(data_list) > 0:
                    return {
                        "username": username,
                        "available": False,
                        "method": "batch_api",
                        "message": "Username is taken",
                        "user_id": data_list[0].get("id")
                    }
                else:
                    # No data returned = username available
                    return {
                        "username": username,
                        "available": True,
                        "method": "batch_api",
                        "message": "Username is available"
                    }
            else:
                return {
                    "username": username,
                    "available": None,
                    "method": "batch_api",
                    "error": f"API returned status {response.status_code}"
                }
        
        except Exception as e:
            return {
                "username": username,
                "available": None,
                "method": "batch_api",
                "error": str(e)
            }
    
    def check_availability_get_user(self, username: str) -> Dict:
        """
        Check availability by attempting to get user info.
        If user exists, username is taken. If 404, username is available.
        
        Args:
            username: Username to check
            
        Returns:
            Dictionary with availability info
        """
        self._enforce_rate_limit()
        
        try:
            response = self.session.get(
                self.USERS_GET_BY_USERNAME_URL,
                params={"username": username},
                timeout=10
            )
            
            if response.status_code == 404:
                return {
                    "username": username,
                    "available": True,
                    "method": "get_user",
                    "message": "Username is available (not found)"
                }
            elif response.status_code == 200:
                data = response.json()
                return {
                    "username": username,
                    "available": False,
                    "method": "get_user",
                    "message": "Username is taken",
                    "user_id": data.get("Id")
                }
            else:
                return {
                    "username": username,
                    "available": None,
                    "method": "get_user",
                    "error": f"Unexpected status code: {response.status_code}"
                }
        
        except requests.exceptions.Timeout:
            return {
                "username": username,
                "available": None,
                "method": "get_user",
                "error": "Request timeout"
            }
        except Exception as e:
            return {
                "username": username,
                "available": None,
                "method": "get_user",
                "error": str(e)
            }
    
    def check_username(self, username: str) -> Dict:
        """
        Check username availability using the most accurate method.
        
        Args:
            username: Username to check
            
        Returns:
            Dictionary with complete availability info
        """
        # First validate format
        is_valid, error_msg = self.validate_format(username)
        if not is_valid:
            return {
                "username": username,
                "available": False,
                "valid_format": False,
                "message": f"Invalid format: {error_msg}"
            }
        
        # Use batch API (most accurate)
        result = self.check_availability_batch(username)
        return {**result, "valid_format": True}
    
    def check_multiple(self, usernames: List[str], verbose: bool = False) -> List[Dict]:
        """
        Check multiple usernames for availability.
        
        Args:
            usernames: List of usernames to check
            verbose: Whether to print progress
            
        Returns:
            List of results for each username
        """
        results = []
        for i, username in enumerate(usernames, 1):
            if verbose:
                print(f"[{i}/{len(usernames)}] Checking '{username}'...", end=" ", flush=True)
            
            result = self.check_username(username)
            results.append(result)
            
            if verbose:
                if result.get("available"):
                    print("✓ AVAILABLE")
                else:
                    print("✗ TAKEN")
        
        return results
    
    def generate_random_username(self, length: int = None, letters_only: bool = False) -> str:
        """
        Generate a random Roblox username.
        
        Args:
            length: Length of username (default random between 3-15)
            letters_only: If True, only use letters. If False, mix letters and numbers
            
        Returns:
            Random username
        """
        if length is None:
            length = random.randint(3, 15)
        
        if letters_only:
            # Only letters
            first_char = random.choice(string.ascii_letters)
            middle_chars = ''.join(random.choices(string.ascii_letters, k=length-2))
            last_char = random.choice(string.ascii_letters)
        else:
            # Mix of letters, numbers, and underscores (but not starting/ending with _)
            first_char = random.choice(string.ascii_letters + string.digits)
            middle_chars = ''.join(random.choices(string.ascii_letters + string.digits + '_', k=length-2))
            last_char = random.choice(string.ascii_letters + string.digits)
        
        return first_char + middle_chars + last_char
    
    def generate_batch_usernames(self, count: int) -> List[str]:
        """
        Generate multiple random usernames.
        
        Args:
            count: How many usernames to generate
            
        Returns:
            List of random usernames
        """
        usernames = []
        while len(usernames) < count:
            username = self.generate_random_username()
            if username not in usernames:  # Avoid duplicates
                usernames.append(username)
        return usernames
    
    def print_result(self, result: Dict):
        """Pretty print a single result."""
        username = result.get("username", "Unknown")
        available = result.get("available")
        
        if available is None:
            print(f"❓ {username}: ERROR - {result.get('error', 'Unknown error')}")
        elif not result.get("valid_format", True):
            print(f"✗ {username}: {result.get('message', 'Invalid format')}")
        elif available:
            print(f"✓ {username}: AVAILABLE")
        else:
            print(f"✗ {username}: TAKEN - {result.get('message', '')}")


def main():
    """Example usage of the RobloxUsernameChecker."""
    
    checker = RobloxUsernameChecker(rate_limit_delay=0.3)
    
    print("=" * 50)
    print("ROBLOX USERNAME AVAILABILITY CHECKER")
    print("=" * 50)
    
    # Interactive mode
    while True:
        print("\nOptions:")
        print("1. Check single username")
        print("2. Check multiple usernames")
        print("3. Auto-generate and check N random usernames")
        print("4. Search 5-letter usernames (letters only)")
        print("5. Search 6-letter usernames (letters only)")
        print("6. Search mixed usernames (letters + numbers)")
        print("7. Exit")
        
        choice = input("Enter choice (1-7): ").strip()
        
        if choice == "1":
            username = input("Enter username to check: ").strip()
            result = checker.check_username(username)
            checker.print_result(result)
        
        elif choice == "2":
            usernames_input = input("Enter usernames separated by commas: ").strip()
            usernames = [u.strip() for u in usernames_input.split(",")]
            results = checker.check_multiple(usernames, verbose=True)
            
            print("\n" + "=" * 50)
            print("SUMMARY:")
            print("=" * 50)
            available = [r for r in results if r.get("available")]
            taken = [r for r in results if r.get("available") is False]
            errors = [r for r in results if r.get("available") is None]
            
            print(f"Available: {len(available)}")
            for r in available:
                print(f"  ✓ {r['username']}")
            
            print(f"\nTaken: {len(taken)}")
            for r in taken:
                print(f"  ✗ {r['username']}")
            
            if errors:
                print(f"\nErrors: {len(errors)}")
                for r in errors:
                    print(f"  ❓ {r['username']}: {r.get('error')}")
        
        elif choice == "3":
            try:
                count = int(input("How many random usernames to generate and check? ").strip())
                if count <= 0:
                    print("Please enter a positive number!")
                    continue
                
                print(f"\nGenerating {count} random usernames...")
                random_usernames = checker.generate_batch_usernames(count)
                
                print(f"Checking availability...\n")
                results = checker.check_multiple(random_usernames, verbose=True)
                
                print("\n" + "=" * 50)
                print("SUMMARY:")
                print("=" * 50)
                available = [r for r in results if r.get("available")]
                taken = [r for r in results if r.get("available") is False]
                errors = [r for r in results if r.get("available") is None]
                
                print(f"\n✓ AVAILABLE ({len(available)}):")
                for r in available:
                    print(f"  • {r['username']}")
                
                print(f"\n✗ TAKEN ({len(taken)}):")
                for r in taken[:10]:  # Show first 10
                    print(f"  • {r['username']}")
                if len(taken) > 10:
                    print(f"  ... and {len(taken) - 10} more")
                
                if errors:
                    print(f"\n❌ ERRORS ({len(errors)}):")
                    for r in errors[:5]:
                        print(f"  • {r['username']}: {r.get('error')}")
            
            except ValueError:
                print("Please enter a valid number!")
        
        elif choice == "4":
            try:
                count = int(input("How many 5-letter usernames to check? ").strip())
                if count <= 0:
                    print("Please enter a positive number!")
                    continue
                
                print(f"\nGenerating {count} random 5-letter usernames (letters only)...")
                random_usernames = [checker.generate_random_username(length=5, letters_only=True) for _ in range(count)]
                random_usernames = list(set(random_usernames))  # Remove duplicates
                
                print(f"Checking {len(random_usernames)} usernames...\n")
                results = checker.check_multiple(random_usernames, verbose=True)
                
                print("\n" + "=" * 50)
                print("SUMMARY (5L - Letters Only):")
                print("=" * 50)
                available = [r for r in results if r.get("available")]
                taken = [r for r in results if r.get("available") is False]
                
                print(f"\n✓ AVAILABLE ({len(available)}):")
                for r in available:
                    print(f"  • {r['username']}")
                
                print(f"\n✗ TAKEN ({len(taken)}):")
                for r in taken[:10]:
                    print(f"  • {r['username']}")
                if len(taken) > 10:
                    print(f"  ... and {len(taken) - 10} more")
            
            except ValueError:
                print("Please enter a valid number!")
        
        elif choice == "5":
            try:
                count = int(input("How many 6-letter usernames to check? ").strip())
                if count <= 0:
                    print("Please enter a positive number!")
                    continue
                
                print(f"\nGenerating {count} random 6-letter usernames (letters only)...")
                random_usernames = [checker.generate_random_username(length=6, letters_only=True) for _ in range(count)]
                random_usernames = list(set(random_usernames))  # Remove duplicates
                
                print(f"Checking {len(random_usernames)} usernames...\n")
                results = checker.check_multiple(random_usernames, verbose=True)
                
                print("\n" + "=" * 50)
                print("SUMMARY (6L - Letters Only):")
                print("=" * 50)
                available = [r for r in results if r.get("available")]
                taken = [r for r in results if r.get("available") is False]
                
                print(f"\n✓ AVAILABLE ({len(available)}):")
                for r in available:
                    print(f"  • {r['username']}")
                
                print(f"\n✗ TAKEN ({len(taken)}):")
                for r in taken[:10]:
                    print(f"  • {r['username']}")
                if len(taken) > 10:
                    print(f"  ... and {len(taken) - 10} more")
            
            except ValueError:
                print("Please enter a valid number!")
        
        elif choice == "6":
            try:
                count = int(input("How many mixed usernames to check (letters + numbers)? ").strip())
                if count <= 0:
                    print("Please enter a positive number!")
                    continue
                
                length = int(input("What length? (e.g., 5, 6, 7): ").strip())
                if length < 3 or length > 20:
                    print("Length must be between 3 and 20!")
                    continue
                
                print(f"\nGenerating {count} random {length}-letter usernames (mixed)...")
                random_usernames = [checker.generate_random_username(length=length, letters_only=False) for _ in range(count)]
                random_usernames = list(set(random_usernames))  # Remove duplicates
                
                print(f"Checking {len(random_usernames)} usernames...\n")
                results = checker.check_multiple(random_usernames, verbose=True)
                
                print("\n" + "=" * 50)
                print(f"SUMMARY ({length}L - Mixed Letters & Numbers):")
                print("=" * 50)
                available = [r for r in results if r.get("available")]
                taken = [r for r in results if r.get("available") is False]
                
                print(f"\n✓ AVAILABLE ({len(available)}):")
                for r in available:
                    print(f"  • {r['username']}")
                
                print(f"\n✗ TAKEN ({len(taken)}):")
                for r in taken[:10]:
                    print(f"  • {r['username']}")
                if len(taken) > 10:
                    print(f"  ... and {len(taken) - 10} more")
            
            except ValueError:
                print("Please enter valid numbers!")
        
        elif choice == "7":
            print("Exiting...")
            break
        
        else:
            print("Invalid choice. Please enter 1-7.")
    
    input("\n\nPress Enter to close...")


if __name__ == "__main__":
    main()
