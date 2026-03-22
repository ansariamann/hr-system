"""Upgrade a user to hr_admin role."""

import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from ats_backend.core.database import db_manager
from ats_backend.auth.models import User


def upgrade_user_to_hr_admin(email: str = None):
    """Upgrade a user to hr_admin role."""
    db_manager.initialize()
    
    try:
        with db_manager.get_session() as session:
            users = session.query(User).all()
            
            if not users:
                print("No users found in database.")
                return
            
            # If no email provided, use first user  
            if not email:
                user = users[0]
                email = user.email
            else:
                user = session.query(User).filter(User.email == email).first()
            
            if not user:
                print(f"User '{email}' not found")
                print("\nAvailable users:")
                for u in users:
                    print(f"  • {u.email} (Role: {u.role or 'None'})")
                return
            
            old_role = user.role
            user.role = "hr_admin"
            session.commit()
            
            print(f"\n✓ User upgraded successfully!")
            print(f"  Email: {user.email}")
            print(f"  Old role: {old_role}")
            print(f"  New role: {user.role}")
            print("\n⚠️  Please log out and log back in to apply the new role.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db_manager.close()


if __name__ == "__main__":
    # Check if email provided as argument
    email = sys.argv[1] if len(sys.argv) > 1 else None
    upgrade_user_to_hr_admin(email)
