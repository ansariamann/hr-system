"""Email templates for the ATS system."""


def render_password_reset_email(
    user_name: str,
    reset_link: str,
    expiry_minutes: int = 30,
) -> str:
    """Render the password reset email as an HTML string.

    Args:
        user_name: Display name or email of the user.
        reset_link: Full URL the user should visit to reset their password.
        expiry_minutes: How many minutes the link remains valid.

    Returns:
        An HTML string ready to be sent as an email body.
    """
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reset Your Password</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f5f7;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f5f7;padding:40px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="480" cellpadding="0" cellspacing="0"
               style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
          <!-- Header -->
          <tr>
            <td style="background-color:#1a1a2e;padding:28px 32px;">
              <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;">HR System</h1>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:32px;">
              <p style="margin:0 0 16px;font-size:16px;color:#333333;">Hi {user_name},</p>
              <p style="margin:0 0 24px;font-size:15px;color:#555555;line-height:1.6;">
                We received a request to reset your password.
                Click the button below to choose a new password.
                This link will expire in <strong>{expiry_minutes} minutes</strong>.
              </p>
              <!-- CTA Button -->
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto 24px;">
                <tr>
                  <td style="border-radius:8px;background-color:#4f46e5;">
                    <a href="{reset_link}"
                       target="_blank"
                       style="display:inline-block;padding:14px 36px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;">
                      Reset Password
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 16px;font-size:13px;color:#888888;line-height:1.5;">
                If the button doesn't work, copy and paste this link into your browser:
              </p>
              <p style="margin:0 0 24px;font-size:13px;color:#4f46e5;word-break:break-all;">
                {reset_link}
              </p>
              <hr style="border:none;border-top:1px solid #eeeeee;margin:24px 0;">
              <p style="margin:0;font-size:12px;color:#aaaaaa;line-height:1.5;">
                If you didn't request this, you can safely ignore this email.
                Your password will not be changed.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color:#f8f9fa;padding:20px 32px;text-align:center;">
              <p style="margin:0;font-size:12px;color:#999999;">
                &copy; HR System &bull; Secure Password Reset
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def render_client_welcome_email(
    client_name: str,
    contact_name: str,
    admin_email: str,
    admin_password: str,
    login_url: str,
    forgot_password_url: str,
) -> str:
    """Render the client welcome email with initial credentials and reset instructions."""
    greeting_name = contact_name or client_name
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your Client Portal Account</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f5f7;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f5f7;padding:40px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0"
               style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
          <tr>
            <td style="background-color:#1a1a2e;padding:28px 32px;">
              <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;">HR System Client Portal</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:32px;">
              <p style="margin:0 0 16px;font-size:16px;color:#333333;">Hi {greeting_name},</p>
              <p style="margin:0 0 20px;font-size:15px;color:#555555;line-height:1.6;">
                Your client account for <strong>{client_name}</strong> has been created successfully.
                Below are your default portal login credentials.
              </p>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:10px;margin:0 0 24px;">
                <tr>
                  <td style="padding:18px 20px;background-color:#fafafa;">
                    <p style="margin:0 0 10px;font-size:14px;color:#666666;">Login Email</p>
                    <p style="margin:0 0 18px;font-size:16px;color:#111111;font-weight:700;">{admin_email}</p>
                    <p style="margin:0 0 10px;font-size:14px;color:#666666;">Temporary Password</p>
                    <p style="margin:0;font-size:16px;color:#111111;font-weight:700;">{admin_password}</p>
                  </td>
                </tr>
              </table>
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
                <tr>
                  <td style="border-radius:8px;background-color:#4f46e5;">
                    <a href="{login_url}"
                       target="_blank"
                       style="display:inline-block;padding:14px 32px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;">
                      Open Client Portal
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 8px;font-size:15px;color:#333333;font-weight:700;">Password Reset Instructions</p>
              <ol style="margin:0 0 20px 18px;padding:0;color:#555555;font-size:14px;line-height:1.7;">
                <li>Sign in once using the temporary email and password above.</li>
                <li>Immediately change your password after login, or use the forgot-password page if needed.</li>
                <li>If you want to reset it directly, open: <a href="{forgot_password_url}" target="_blank" style="color:#4f46e5;text-decoration:none;">Reset Password</a></li>
              </ol>
              <p style="margin:0 0 10px;font-size:13px;color:#888888;">Portal login URL:</p>
              <p style="margin:0 0 16px;font-size:13px;color:#4f46e5;word-break:break-all;">{login_url}</p>
              <p style="margin:0 0 10px;font-size:13px;color:#888888;">Forgot password URL:</p>
              <p style="margin:0;font-size:13px;color:#4f46e5;word-break:break-all;">{forgot_password_url}</p>
            </td>
          </tr>
          <tr>
            <td style="background-color:#f8f9fa;padding:20px 32px;text-align:center;">
              <p style="margin:0;font-size:12px;color:#999999;">
                This is your client creation acknowledgement and access email from HR System.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def render_client_welcome_email_text(
    client_name: str,
    contact_name: str,
    admin_email: str,
    admin_password: str,
    login_url: str,
    forgot_password_url: str,
) -> str:
    """Render the client welcome email as plain text."""
    greeting_name = contact_name or client_name
    return f"""HR System Client Portal

Hi {greeting_name},

Your client account for {client_name} has been created successfully.

Default login credentials:
- Login Email: {admin_email}
- Temporary Password: {admin_password}

Portal login URL:
{login_url}

Password reset instructions:
1. Sign in once using the temporary email and password above.
2. Immediately change your password after login, or use the forgot-password page if needed.
3. If you want to reset it directly, open the forgot-password page below.

Forgot password URL:
{forgot_password_url}

This message is your client creation acknowledgement and access email from HR System.
"""


def render_client_invite_email(
    user_name: str,
    client_name: str,
    setup_link: str,
    expiry_minutes: int = 30,
) -> str:
    """Render a client portal invitation email as an HTML string."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Set Up Your Client Portal Access</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f5f7;font-family:Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f5f7;padding:40px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="520" cellpadding="0" cellspacing="0"
               style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
          <tr>
            <td style="background-color:#1a1a2e;padding:28px 32px;">
              <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;">HR System Client Portal</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:32px;">
              <p style="margin:0 0 16px;font-size:16px;color:#333333;">Hi {user_name},</p>
              <p style="margin:0 0 24px;font-size:15px;color:#555555;line-height:1.6;">
                Your portal access for <strong>{client_name}</strong> is ready.
                Use the button below to set your password and activate your client portal access.
                This link expires in <strong>{expiry_minutes} minutes</strong>.
              </p>
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto 24px;">
                <tr>
                  <td style="border-radius:8px;background-color:#4f46e5;">
                    <a href="{setup_link}"
                       target="_blank"
                       style="display:inline-block;padding:14px 36px;font-size:15px;font-weight:600;color:#ffffff;text-decoration:none;">
                      Set Password
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 16px;font-size:13px;color:#888888;line-height:1.5;">
                If the button doesn't work, copy and paste this link into your browser:
              </p>
              <p style="margin:0 0 24px;font-size:13px;color:#4f46e5;word-break:break-all;">
                {setup_link}
              </p>
              <hr style="border:none;border-top:1px solid #eeeeee;margin:24px 0;">
              <p style="margin:0;font-size:12px;color:#aaaaaa;line-height:1.5;">
                If you were not expecting this invitation, contact your HR System administrator.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def render_client_invite_email_text(
    user_name: str,
    client_name: str,
    setup_link: str,
    expiry_minutes: int = 30,
) -> str:
    """Render a client portal invitation email as plain text."""
    return f"""HR System Client Portal

Hi {user_name},

Your portal access for {client_name} is ready.

Use the link below to set your password and activate your client portal access.
This link expires in {expiry_minutes} minutes.

{setup_link}

If you were not expecting this invitation, contact your HR System administrator.
"""
