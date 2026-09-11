from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)

_CONTACT_EMAIL = "arturdamaceno.dev@gmail.com"
_BUSINESS_NAME = "Artur Damaceno"
_BUSINESS_PHONE = "+55 51 99913-0114"

_PAGE = """<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Hermes</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 42rem; margin: 3rem auto; padding: 0 1.25rem;
         line-height: 1.6; color: #1c1c1c; }}
  h1 {{ font-size: 1.6rem; }}
  h2 {{ font-size: 1.1rem; margin-top: 2rem; }}
  footer {{ margin-top: 3rem; font-size: .85rem; color: #666; }}
</style>
</head>
<body>
{body}
<footer>Contato: <a href="mailto:{email}">{email}</a></footer>
</body>
</html>
"""

_PRIVACY_BODY = """
<h1>Política de Privacidade</h1>
<p>O Hermes é um assistente de atendimento que responde mensagens diretas recebidas nas contas
profissionais do Instagram administradas pelo próprio responsável do aplicativo. O aplicativo não é
oferecido a terceiros.</p>

<h2>Dados que tratamos</h2>
<ul>
  <li>Identificador da conversa no Instagram (Instagram-scoped ID) de quem envia a mensagem.</li>
  <li>Conteúdo das mensagens trocadas na conversa.</li>
  <li>Dados de contato que a própria pessoa informa na conversa, quando pede atendimento humano.</li>
</ul>

<h2>Como usamos</h2>
<p>Os dados são usados apenas para responder a conversa, dar continuidade ao atendimento e encaminhar
o contato para uma pessoa quando necessário. Não vendemos, alugamos nem compartilhamos os dados com
terceiros para publicidade.</p>

<h2>Retenção</h2>
<p>O histórico da conversa é mantido enquanto for necessário para o atendimento e é apagado quando
deixa de ser útil ou quando a pessoa solicita.</p>

<h2>Exclusão de dados</h2>
<p>Para pedir a exclusão dos seus dados, envie um e-mail para o endereço abaixo informando o seu
@ do Instagram. A exclusão é feita em até 30 dias.</p>

<h2>Seus direitos</h2>
<p>Você pode solicitar acesso, correção ou exclusão dos seus dados pelo e-mail de contato.</p>
"""

_TERMS_BODY = """
<h1>Termos de Serviço</h1>
<p>O Hermes é um assistente de atendimento usado pelo responsável do aplicativo para responder
mensagens diretas nas contas profissionais do Instagram que ele mesmo administra.</p>

<h2>Uso</h2>
<p>O aplicativo é de uso próprio e não é disponibilizado a outras empresas ou pessoas.</p>

<h2>Conteúdo das respostas</h2>
<p>As respostas são geradas automaticamente e podem conter erros. Informações sobre preços,
disponibilidade e condições devem ser confirmadas com o atendimento humano.</p>

<h2>Limitação de responsabilidade</h2>
<p>O aplicativo é fornecido no estado em que se encontra, sem garantia de disponibilidade contínua.</p>

<h2>Alterações</h2>
<p>Estes termos podem ser atualizados. A versão vigente é sempre a publicada nesta página.</p>
"""


@router.get("/", response_class=HTMLResponse)
def landing() -> str:
    body = f"""
<h1>{_BUSINESS_NAME}</h1>
<p>Atendimento automatizado para contas profissionais do Instagram. O Hermes responde as mensagens
diretas recebidas na conta, apresenta os produtos e serviços do catálogo e encaminha o contato para
atendimento humano quando a pessoa pede.</p>

<h2>O que fazemos</h2>
<ul>
  <li>Resposta automática a mensagens diretas do Instagram.</li>
  <li>Apresentação de catálogo, preços e condições.</li>
  <li>Encaminhamento do contato para atendimento humano.</li>
</ul>

<h2>Contato</h2>
<p>E-mail: <a href="mailto:{_CONTACT_EMAIL}">{_CONTACT_EMAIL}</a><br>
Telefone: {_BUSINESS_PHONE}</p>

<h2>Documentos</h2>
<p><a href="/privacy">Política de Privacidade</a> &middot;
<a href="/terms">Termos de Serviço</a> &middot;
<a href="/data-deletion">Exclusão de dados</a></p>
"""
    return _PAGE.format(title=_BUSINESS_NAME, body=body, email=_CONTACT_EMAIL)


@router.get("/privacy", response_class=HTMLResponse)
def privacy_policy() -> str:
    return _PAGE.format(title="Política de Privacidade", body=_PRIVACY_BODY, email=_CONTACT_EMAIL)


@router.get("/terms", response_class=HTMLResponse)
def terms_of_service() -> str:
    return _PAGE.format(title="Termos de Serviço", body=_TERMS_BODY, email=_CONTACT_EMAIL)


@router.get("/data-deletion", response_class=HTMLResponse)
def data_deletion() -> str:
    body = """
<h1>Exclusão de dados</h1>
<p>Para excluir os dados da sua conversa com o Hermes, envie um e-mail para o endereço abaixo com o
assunto "Exclusão de dados" e informe o seu @ do Instagram.</p>
<p>A exclusão é concluída em até 30 dias e você recebe uma confirmação por e-mail.</p>
"""
    return _PAGE.format(title="Exclusão de dados", body=body, email=_CONTACT_EMAIL)
