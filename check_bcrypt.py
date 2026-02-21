
import bcrypt
print(f"Dir: {dir(bcrypt)}")
try:
    print(f"Version: {bcrypt.__version__}")
except Exception as e:
    print(f"No version: {e}")

try:
    print(f"About version: {bcrypt.__about__.__version__}")
except Exception as e:
    print(f"No about: {e}")
