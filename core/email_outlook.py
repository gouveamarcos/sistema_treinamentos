from django.core.mail.backends.base import BaseEmailBackend


class OutlookEmailBackend(BaseEmailBackend):
    # Envia pelo Outlook instalado no Windows, com a conta que esta aberta
    # nele. Nao precisa de senha: usa o login do proprio Windows/Outlook.
    def send_messages(self, email_messages):
        try:
            import pythoncom
            import win32com.client
        except ImportError:
            if self.fail_silently:
                return 0
            raise RuntimeError(
                "Para enviar pelo Outlook, instale o pywin32: "
                "venv\\Scripts\\pip install -r requirements.txt"
            )

        enviados = 0
        pythoncom.CoInitialize()
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            for mensagem in email_messages:
                if not mensagem.recipients():
                    continue
                item = outlook.CreateItem(0)
                item.To = ";".join(mensagem.to)
                item.CC = ";".join(mensagem.cc)
                item.BCC = ";".join(mensagem.bcc)
                item.Subject = mensagem.subject
                item.Body = mensagem.body
                item.Send()
                enviados += 1
        except Exception:
            if not self.fail_silently:
                raise
        finally:
            pythoncom.CoUninitialize()
        return enviados
