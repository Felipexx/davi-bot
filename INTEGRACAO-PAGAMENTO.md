# 📑 Integração de Pagamento → liberar acesso no bot Davi

> **Para o desenvolvedor do site (ou para o outro chat):** este documento descreve
> EXATAMENTE como o site deve avisar o bot Davi que alguém assinou, pra liberar o
> acesso no WhatsApp automaticamente. Siga o formato à risca — principalmente o
> formato do telefone.

---

## Como funciona o acesso

O bot Davi tem um endpoint pronto que ativa um assinante. Quando o pagamento é
**aprovado** no Mercado Pago, o seu site (ou o webhook do Mercado Pago no seu
backend) deve fazer **uma chamada HTTP** pro Davi com o telefone da pessoa.

## A chamada que o site deve fazer

- **Método:** `POST`
- **URL:** `https://SEU-APP.onrender.com/payment-webhook`
  *(troque pelo endereço real do bot no Render)*
- **Cabeçalho obrigatório:**
  ```
  X-Webhook-Secret: <igual ao PAYMENT_WEBHOOK_SECRET configurado no Render>
  Content-Type: application/json
  ```
- **Corpo (JSON):**
  ```json
  {
    "telefone": "5515976004427",
    "status": "approved",
    "expira_em": "2026-07-04T00:00:00+00:00"
  }
  ```

### Respostas do Davi
- `200 OK` + `{"status":"ok"}` → assinante ativado com sucesso.
- `403` → o `X-Webhook-Secret` está errado/ausente.
- `400` → faltou o campo `telefone`.

---

## ⚠️ REGRA MAIS IMPORTANTE: formato do telefone

O `telefone` precisa ser **somente números, começando com 55** (código do Brasil)
+ DDD + número. É esse formato que "casa" com o número que o WhatsApp envia.

| Exemplo | Vale? |
|---|---|
| `5515976004427` | ✅ Sim |
| `(15) 97600-4427` | ❌ Não (tem símbolos) |
| `+5515976004427` | ❌ Não (tem o `+`) |
| `15976004427` | ❌ Não (falta o `55`) |

**Como normalizar no site (regra):**
1. Apague tudo que não for número (espaços, `(`, `)`, `-`, `+`).
2. Se não começar com `55`, coloque `55` na frente.
3. Resultado esperado: `55` + DDD (2 dígitos) + número (9 dígitos) = **13 dígitos**.

> 🔴 Se isso estiver errado, a pessoa **paga mas não é liberada**. É o erro nº 1.
> O número informado no checkout TEM que ser o mesmo que ela usa no WhatsApp.

---

## Campo `status`

O Davi ativa o assinante se o `status` enviado for um destes:
`ativo`, `active`, `paid`, `approved`, `completed`.

No Mercado Pago, um pagamento aprovado costuma vir como `approved`, e uma
assinatura (preapproval) ativa como `authorized` → nesse caso, **mande
`"status": "approved"`** pro Davi (ou mapeie pra um dos valores aceitos acima).

## Campo `expira_em` (data de expiração)

Texto no formato ISO 8601, em UTC. Calcule a partir do momento do pagamento:
- **Plano mensal:** agora + **30 dias** → ex.: `"2026-07-04T00:00:00+00:00"`
- **Plano anual:** agora + **365 dias**

Se você **não** mandar `expira_em`, o assinante fica ativo sem data de expiração
(não recomendado pra assinatura — sempre mande a data).

---

## Captura do WhatsApp no Mercado Pago (importante)

O Mercado Pago, no webhook, geralmente manda só um **ID do pagamento** — você
precisa consultar a API do MP pra pegar os detalhes. Pra o **telefone do WhatsApp**
voltar, capriche no checkout:

- Guarde o WhatsApp digitado em **`metadata`** ou **`external_reference`** ao criar
  o pagamento/assinatura no Mercado Pago.
- No webhook, leia esse `metadata`/`external_reference`, normalize o telefone
  (regra acima) e então chame o `/payment-webhook` do Davi.

---

## Como testar de ponta a ponta

1. Faça uma assinatura de teste (sandbox do Mercado Pago).
2. Olhe os **Logs do Render** do bot Davi. Deve aparecer:
   ```
   Pagamento processado: 5515976004427 -> ativo=True
   ```
3. Mande uma mensagem no WhatsApp **com esse mesmo número** → o Davi deve
   responder como **assinante** (sem o limite de mensagens grátis).

### Teste rápido sem pagar (simulando a chamada)
```bash
curl -X POST https://SEU-APP.onrender.com/payment-webhook \
  -H "X-Webhook-Secret: SEU_SEGREDO" \
  -H "Content-Type: application/json" \
  -d '{"telefone":"5515976004427","status":"approved","expira_em":"2026-07-04T00:00:00+00:00"}'
```
Se voltar `{"status":"ok"}`, a liberação está funcionando. 🎉

---

## Resumo (checklist pro site)
- [ ] Chama `POST /payment-webhook` do Davi quando o pagamento é aprovado.
- [ ] Envia o cabeçalho `X-Webhook-Secret` igual ao do Render.
- [ ] `telefone` só com números, começando com `55` (13 dígitos no total).
- [ ] `status` = `approved` (ou outro da lista aceita).
- [ ] `expira_em` calculado (30 dias mensal / 365 dias anual), em ISO/UTC.
- [ ] Testado: log do Render mostra "ativo=True" e o WhatsApp libera.
