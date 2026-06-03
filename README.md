# Davi 🙏 — Bot de WhatsApp (com IA Gemini)

O **Davi** é um amigo de fé que conversa pelo WhatsApp: acolhe a pessoa, traz uma
palavra de ânimo com base na Bíblia e ora junto. É um produto por **assinatura**,
com um **devocional diário** enviado aos assinantes.

Este guia é feito **para quem não programa**. Vá com calma, um passo de cada vez.
Se travar em algum ponto, **copie a mensagem de erro** e peça ajuda ao Claude Code.

---

## 📁 O que tem neste projeto

| Arquivo | Pra que serve |
|---|---|
| `app.py` | O servidor que recebe e responde as mensagens do WhatsApp |
| `ia.py` | A conversa com a IA (Gemini). Trocar de IA no futuro? Mexe só aqui |
| `davi_persona.py` | A "personalidade" do Davi (o jeitão dele). Ajuste o tom aqui |
| `whatsapp.py` | Envio de mensagens e templates pelo WhatsApp |
| `db.py` | O banco de dados (usuários, assinantes, histórico) |
| `assinaturas.py` | A regra de quem pode conversar (assinante ou mensagens grátis) |
| `devocional_diario.py` | Envia o devocional do dia (roda 1x por dia) |
| `config.py` | Lê as configurações do arquivo `.env` |
| `.env.example` | Modelo das "chaves" e configurações. Você copia pra `.env` |
| `README.md` | Este guia |

---

## ✅ O que você vai precisar (contas)

1. **Meta for Developers** — https://developers.facebook.com (pro WhatsApp).
2. **WhatsApp Cloud API** — ativada dentro do app da Meta (passo 2 abaixo).
3. **Google AI Studio** — https://aistudio.google.com (pra chave do Gemini).
4. **Render** — https://render.com (pra hospedar o bot na internet, de graça pra começar).
5. **GitHub** — https://github.com (pra guardar o código e conectar ao Render).

> Todas têm planos gratuitos pra começar. Crie as contas com calma.

---

## 🧪 Passo 1 — Testar no seu computador (opcional, mas recomendado)

> No Windows, use `py` no lugar de `python`. Se você usa Mac/Linux, troque `py` por `python3`.

1. Abra o terminal **dentro da pasta do projeto**.
2. Instale as dependências:
   ```
   py -m pip install -r requirements.txt
   ```
3. Crie o arquivo de configuração: copie `.env.example` e renomeie a cópia para `.env`.
   Preencha o que tiver (pode deixar em branco o que ainda não tem — o bot sobe assim mesmo).
4. Rode o servidor:
   ```
   py -m uvicorn app:app --reload
   ```
5. Abra no navegador: http://127.0.0.1:8000
   Se aparecer **"Davi está no ar 🙏"**, está funcionando! 🎉

Pra a Meta enviar mensagens pro seu computador durante o teste, você precisaria de
um "túnel" (ex.: **ngrok**). Mas isso é avançado — o jeito mais simples é seguir
direto pro deploy no Render (passo 5) e testar lá.

---

## 🔑 Passo 2 — Pegar as credenciais do WhatsApp (Meta)

1. Entre em https://developers.facebook.com e crie um app (tipo **"Empresa/Business"**).
2. No painel do app, adicione o produto **"WhatsApp"**.
3. Em **WhatsApp → Configuração da API**, você verá:
   - Um **número de teste** e o **Phone Number ID** → copie o **Phone Number ID**.
   - Um **token de acesso temporário** (dura 24h) → serve pra testar.
4. **Token permanente** (recomendado pra valer): crie um **System User** em
   **Configurações do Negócio → Usuários do sistema**, dê a ele a permissão do
   app de WhatsApp e gere um token permanente. Guarde esse token com cuidado.
5. **Verify Token**: invente uma senha qualquer (ex.: `davi-segredo-123`). Você vai
   usar ela em DOIS lugares: aqui na Meta (passo 5) e no seu `.env`
   (`WHATSAPP_VERIFY_TOKEN`). Tem que ser **idêntica** nos dois.

No final você precisa ter em mãos:
- `WHATSAPP_TOKEN` (o token, de preferência o permanente)
- `WHATSAPP_PHONE_NUMBER_ID` (o Phone Number ID)
- `WHATSAPP_VERIFY_TOKEN` (a senha que você inventou)

---

## 🤖 Passo 3 — Pegar a chave do Gemini (Google)

1. Entre em https://aistudio.google.com
2. Clique em **"Get API key" / "Criar chave de API"**.
3. Copie a chave. Ela é o seu `GEMINI_API_KEY`.

---

## ☁️ Passo 4 — Subir o bot no Render

1. Suba esta pasta pro **GitHub** (crie um repositório e envie os arquivos).
   > O `.gitignore` já garante que o `.env` e o banco **não** sejam enviados. 👍
2. No **Render**, clique em **New → Web Service** e conecte seu repositório do GitHub.
3. Configure assim:
   - **Build Command:**
     ```
     pip install -r requirements.txt
     ```
   - **Start Command:**
     ```
     uvicorn app:app --host 0.0.0.0 --port $PORT
     ```
4. Em **Environment** (Variáveis de Ambiente), adicione **uma a uma** as chaves do
   seu `.env` (mesmos nomes e valores):
   `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`,
   `GEMINI_API_KEY`, `GEMINI_MODEL`, `FREE_MESSAGES`, `LINK_ASSINATURA`,
   `DEVOTIONAL_TEMPLATE_NAME`, `DATABASE_PATH`, `ADMIN_TOKEN`, `PAYMENT_WEBHOOK_SECRET`.
5. Clique em **Create Web Service** e espere o deploy terminar.
6. O Render vai te dar um endereço, algo como:
   `https://seu-app.onrender.com`
   Abra ele no navegador: deve mostrar **"Davi está no ar 🙏"**.

> ⚠️ **Importante sobre o banco no Render:** veja a seção "Avisos honestos" no fim
> deste guia. No plano grátis, o arquivo do banco pode ser apagado quando o
> servidor reinicia. Pra valer de verdade, use um **disco persistente** ou um
> banco gerenciado (Postgres).

---

## 🔗 Passo 5 — Conectar o webhook na Meta

1. No painel do app da Meta, vá em **WhatsApp → Configuração** (Webhooks).
2. Em **Callback URL**, coloque o endereço do seu bot **com `/webhook` no fim**:
   ```
   https://seu-app.onrender.com/webhook
   ```
3. Em **Verify Token**, digite **a mesma senha** que está no seu `WHATSAPP_VERIFY_TOKEN`.
4. Clique em **Verificar e salvar**. Se der certo, ótimo! ✅
5. Em **Webhook fields**, clique em **Manage** e **assine o campo `messages`**.

---

## 💬 Passo 6 — Testar de verdade

1. No seu WhatsApp, mande uma mensagem pro número configurado na Meta.
   > No modo de teste da Meta, só números que você **adicionou como destinatários
   > permitidos** conseguem conversar. Adicione o seu número lá pra testar.
2. O Davi deve responder em alguns segundos. 🎉
3. Mande algumas mensagens: depois de `FREE_MESSAGES` (padrão 3), quem **não é
   assinante** recebe o convite pra assinar.

---

## 📿 Passo 7 — Devocional diário

O devocional vai pra pessoa "do nada" (sem ela ter mandado mensagem antes). Por
regra da Meta, isso **só** é permitido com um **template aprovado**.

1. No **WhatsApp Manager → Modelos de mensagem**, crie um template:
   - **Categoria:** Utility (Utilitário)
   - **Idioma:** Português (BR) → `pt_BR`
   - **Corpo:** um texto com **uma variável** `{{1}}`. Exemplo:
     ```
     {{1}}
     ```
     (ou algo como: `Mensagem do Davi pra você hoje:\n\n{{1}}`)
   - Dê um **nome** ao template (ex.: `devocional_diario`).
2. Espere a **aprovação** da Meta (costuma levar de minutos a algumas horas).
3. Coloque o **nome do template** no `.env`, em `DEVOTIONAL_TEMPLATE_NAME`
   (e também na variável de ambiente do Render).
4. **Agende** o envio pra rodar 1x por dia. Duas opções:
   - **Cron Job do Render:** crie um **New → Cron Job** apontando pro mesmo
     repositório, com o comando:
     ```
     python devocional_diario.py
     ```
     e a agenda (ex.: todo dia às 8h: `0 11 * * *` — atenção: o Render usa o
     fuso **UTC**; 8h no horário de Brasília ≈ 11h UTC).
   - **cron-job.org:** alternativa gratuita que "chama" uma URL num horário. Nesse
     caso você precisaria de um endpoint que dispara o envio (dá pra adicionar
     depois, se preferir esse caminho).

> 💡 O texto do devocional é gerado pela IA. Se a IA falhar no momento do envio, o
> próprio script usa uma **lista de reserva** de devocionais prontos (que você pode
> editar dentro de `devocional_diario.py`).

---

## 💳 Passo 8 — Pagamentos (assinaturas)

Quando alguém paga, o bot precisa marcar essa pessoa como **assinante ativo**.

**No comecinho (manual):** você pode adicionar assinantes na mão chamando o
endpoint `/admin/assinante`. Exemplo (no terminal):
```
curl -X POST https://seu-app.onrender.com/admin/assinante ^
  -H "X-Admin-Token: SEU_ADMIN_TOKEN" ^
  -H "Content-Type: application/json" ^
  -d "{\"telefone\":\"5511999998888\",\"ativo\":true}"
```
> No Windows, o `^` quebra a linha no terminal. No Mac/Linux, use `\`.

**Automático (recomendado depois):** ligue o webhook do seu gateway de pagamento
(ex.: **AbacatePay**, **Mercado Pago**) pro endpoint:
```
https://seu-app.onrender.com/payment-webhook
```
O endpoint já vem pronto e protegido por `PAYMENT_WEBHOOK_SECRET`. Como cada
gateway envia os dados de um jeito diferente, há um trecho comentado em `app.py`
(função `payment_webhook`) pra você (ou o Claude Code) **adaptar aos campos do seu
gateway** (de onde tirar o telefone e a data de expiração).

---

## ⚠️ Avisos honestos (leia!)

- **O banco pode sumir:** em planos grátis, o arquivo `davi.db` pode ser apagado
  quando o servidor reinicia. Pra produção de verdade, configure um **disco
  persistente** no Render (e aponte `DATABASE_PATH` pra ele) ou migre pra um banco
  gerenciado (**Postgres**). Como o acesso ao banco está isolado em `db.py`, essa
  troca no futuro é tranquila.
- **Custos:** você paga (a) os **tokens do Gemini** por conversa, (b) as **mensagens
  da Meta** — e atenção: **templates do devocional são cobrados por envio**, então
  mandar pra base inteira todo dia é o que mais pesa — e (c) a **hospedagem**. As
  conversas iniciadas pela própria pessoa costumam ser baratas/gratuitas.
- **Segurança:** **nunca** mostre ou suba seus tokens (`.env` fica fora do GitHub).
  Mantenha os endpoints `/admin/assinante` e `/payment-webhook` protegidos pelos
  segredos. Se desconfiar que um token vazou, gere um novo.
- **Travou?** Copie a mensagem de erro (do terminal ou dos **Logs** do Render) e
  peça ajuda ao Claude Code. 🙏

---

Feito com carinho pra abençoar pessoas. 💙
