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
