from unittest.mock import MagicMock, patch

from notifications.email_sender import SmtpEmailSender


def test_smtp_email_sender_sends_a_well_formed_message():
    """El suite de pytest no depende de Docker (Mailpit real se verifico
    aparte, TASK-0034): aqui se verifica que SmtpEmailSender construye y
    envia el mensaje correctamente mockeando smtplib.SMTP.
    """
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client

    with patch("smtplib.SMTP", return_value=mock_client) as mock_smtp:
        SmtpEmailSender().send(to="padre@example.com", subject="Asunto", body="Cuerpo del mensaje")

    mock_smtp.assert_called_once()
    mock_client.send_message.assert_called_once()
    sent_message = mock_client.send_message.call_args[0][0]
    assert sent_message["To"] == "padre@example.com"
    assert sent_message["Subject"] == "Asunto"
    assert sent_message.get_content().strip() == "Cuerpo del mensaje"
