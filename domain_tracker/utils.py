from django.core.mail import EmailMultiAlternatives
from django.conf import settings


def send_combined_expiry_mail(subject, services, recipient):

    # TEXT VERSION
    text_content = "Expiry Summary:\n\n"
    for s in services:
        text_content += f"{s['type']}: {s['name']} - {s['days_left']} days left (Expiry: {s['expiry_date']})\n"

    # HTML rows (ONLY expiring ones)
    rows = ""
    for s in services:
        if s['days_left'] <= 0:
            status = "Expired"
            color = "#ef4444"
            bg = "#fee2e2"
        elif s['days_left'] <= 7:
            status = f"{s['days_left']} days left"
            color = "#f59e0b"
            bg = "#fef3c7"
        else:
            status = f"{s['days_left']} days left"
            color = "#3b82f6"
            bg = "#dbeafe"

        rows += f"""
        <tr style="border-bottom:1px solid #e5e7eb;">
            <td style="font-size:14px; color:#374151;">{s['type']}</td>
            <td style="font-size:14px; color:#111827; font-weight:600;">{s['name']}</td>
            <td style="font-size:14px; color:#6b7280;">{s['expiry_date']}</td>
            <td>
                <span style="
                    background:{bg};
                    color:{color};
                    padding:5px 12px;
                    border-radius:20px;
                    font-size:12px;
                    font-weight:600;
                    display:inline-block;
                ">
                    {status}
                </span>
            </td>
        </tr>
        """

    # HTML CONTENT
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0; padding:0; background:#eef2f7; font-family:Segoe UI, Arial, sans-serif;">

    <div style="max-width:650px; margin:30px auto; background:#ffffff; border-radius:14px; overflow:hidden; box-shadow:0 10px 30px rgba(0,0,0,0.08);">

        <!-- HEADER -->
        <div style="background:linear-gradient(135deg,#4f46e5,#7c3aed); padding:25px; text-align:center;">
            <h1 style="color:#ffffff; margin:0; font-size:22px;">🚨 Expiry Alert</h1>
            <p style="color:#d1d5db; margin-top:6px; font-size:13px;">
                Domain Management Notification
            </p>
        </div>

        <!-- BODY -->
        <div style="padding:25px;">

            <p style="font-size:15px; color:#374151;">Hello Admin,</p>

            <p style="font-size:14px; color:#6b7280; line-height:1.6;">
                The following services require your attention.
            </p>

            <table width="100%" cellpadding="10" cellspacing="0" style="border-collapse:collapse; margin-top:20px;">
                <tr style="background:#f3f4f6; text-align:left;">
                    <th>Service</th>
                    <th>Name</th>
                    <th>Expiry Date</th>
                    <th>Status</th>
                </tr>
                {rows}
            </table>

            <div style="margin-top:25px; padding:15px; background:#fef3c7; border-radius:8px;">
                <p style="margin:0; font-size:14px; color:#92400e;">
                    ⚠️ Please renew services to avoid downtime.
                </p>
            </div>

        </div>

        <!-- FOOTER -->
        <div style="background:#f9fafb; padding:15px; text-align:center;">
            <p style="font-size:12px; color:#9ca3af; margin:0;">
                This is an automated email.
            </p>
        </div>

    </div>

    </body>
    </html>
    """

    # SEND EMAIL
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.EMAIL_HOST_USER,
        to=[recipient]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()