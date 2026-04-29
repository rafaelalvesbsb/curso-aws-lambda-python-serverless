# Account Information Schemas

## 📋 Visão Geral

Este documento explica como usar os schemas Pydantic para a API de **Dados Cadastrais** do BTG Pactual.

**Endpoint da API:** `/api/v1/account-management/account/{accountNumber}/information`

**Referência:** `docs/sources/btg/api/API de Dados Cadastrais.yaml`

---

## 🎯 Dois Schemas, Dois Momentos

### 1️⃣ `AccountInformationRaw` - JSON Aninhado da API

Use este schema para **validar o JSON RAW** que vem diretamente da API BTG.

**Estrutura:**
```json
{
  "accountNumber": "000123456",
  "holder": {
    "name": "José Antônio Silva",
    "taxIdentification": "12345678900"
  },
  "coHolders": [
    {
      "name": "Maria Helena Costa",
      "taxIdentification": "98765432100"
    }
  ],
  "users": [
    {
      "name": "José Antônio Silva",
      "userEmail": "jose.antonio@email.com",
      "phoneNumber": "11-99221-4894",
      "isOwner": true
    }
  ]
}
```

**Uso:**
```python
from src.btg.schemas.account_information import AccountInformationRaw

# Valida JSON da API
account = AccountInformationRaw(**api_response)
print(account.accountNumber)      # "000123456"
print(account.holder.name)         # "José Antônio Silva"
print(account.users[0].userEmail) # "jose.antonio@email.com"
```

---

### 2️⃣ `AccountInformationFlat` - DataFrame Normalizado

Use este schema para **validar o DataFrame FLAT** após o processamento.

**Fluxo de Processamento:**
1. `_flat_users_key()` → achata array `users` em `user_0_name`, `user_1_name`, etc
2. `pd.json_normalize()` → achata objetos nested em `holder.name`, `coHolder.name`
3. `rename(BTG_ACCOUNT_API_TO_STANDARD)` → renomeia para padrão interno

**Estrutura após processamento:**
```python
{
  "account_number": "000123456",
  "holder_name": "José Antônio Silva",
  "holder_tax_id": "12345678900",
  "primary_user_name": "José Antônio Silva",
  "primary_user_email": "jose.antonio@email.com",
  "primary_user_phone": "11-99221-4894",
  "primary_user_is_owner": True,
  "secondary_user_name": None,
  "secondary_user_email": None,
  "co_holder_name": "Maria Helena Costa",
  "co_holder_tax_id": "98765432100"
}
```

**Uso:**
```python
from src.btg.schemas.account_information import AccountInformationFlat

# Após processar o DataFrame
df_dict = df.to_dict('records')[0]
account_flat = AccountInformationFlat(**df_dict)
print(account_flat.account_number)        # "000123456"
print(account_flat.primary_user_email)    # "jose.antonio@email.com"
```

---

## 🔄 Integração com Código Existente

### Função: `create_list_users_info()` (src/util/helpers.py)

**Antes:**
```python
def create_list_users_info(users_accounts: list) -> list[dict]:
    users_info = []
    for account in users_accounts:
        user = get_account_holder_user_info(account)
        if 'users' not in user.keys() or user['users'] == []:
            user['users'] = [{'name': 'users_info_unavailable'}]
        normalized_user = _flat_users_key(user)
        users_info.append(normalized_user)
    return users_info
```

**Depois (com validação):**
```python
from src.btg.schemas.account_information import AccountInformationRaw

def create_list_users_info(users_accounts: list) -> list[dict]:
    users_info = []
    for account in users_accounts:
        user = get_account_holder_user_info(account)

        # ✅ VALIDAÇÃO DO JSON RAW
        try:
            AccountInformationRaw(**user)
        except Exception as e:
            logger.warning(f"Validation error for account {account}: {e}")

        if 'users' not in user.keys() or user['users'] == []:
            user['users'] = [{'name': 'users_info_unavailable'}]
        normalized_user = _flat_users_key(user)
        users_info.append(normalized_user)
    return users_info
```

---

### Função: `upsert_account_users_info_parquet()` (src/tmp/handles_data_transformation.py)

**Linha 1077-1083 (Atual):**
```python
new_users_info = create_list_users_info(list(new_ids))

df_new_users_info = pd.json_normalize(new_users_info)

df_new_users_info = df_new_users_info.rename(columns=BTG_ACCOUNT_API_TO_STANDARD)

df_new_users_info = df_new_users_info.reindex(columns=list(BTG_ACCOUNT_API_TO_STANDARD.values()))
```

**Depois (com validação do DataFrame flat):**
```python
from src.btg.schemas.account_information import AccountInformationFlat

new_users_info = create_list_users_info(list(new_ids))

df_new_users_info = pd.json_normalize(new_users_info)
df_new_users_info = df_new_users_info.rename(columns=BTG_ACCOUNT_API_TO_STANDARD)
df_new_users_info = df_new_users_info.reindex(columns=list(BTG_ACCOUNT_API_TO_STANDARD.values()))

# ✅ VALIDAÇÃO DO DATAFRAME FLAT
for idx, row in df_new_users_info.iterrows():
    try:
        AccountInformationFlat(**row.to_dict())
    except Exception as e:
        logger.warning(f"Validation error for row {idx}: {e}")
```

---

## 📊 Mapeamento de Campos

### API → DataFrame (BTG_ACCOUNT_API_TO_STANDARD)

| Campo na API (após flatten) | Campo no DataFrame | Observação |
|------------------------------|-------------------|------------|
| `accountNumber` | `account_number` | ID da conta |
| `holder.name` | `holder_name` | Nome do titular |
| `holder.taxIdentification` | `holder_tax_id` | CPF/CNPJ do titular |
| `user_0_name` | `primary_user_name` | Primeiro usuário |
| `user_0_userEmail` | `primary_user_email` | Email do 1º usuário |
| `user_0_phoneNumber` | `primary_user_phone` | Telefone do 1º usuário |
| `user_0_isOwner` | `primary_user_is_owner` | Proprietário? |
| `user_1_name` | `secondary_user_name` | Segundo usuário |
| `user_1_userEmail` | `secondary_user_email` | Email do 2º usuário |
| `user_2_name` | `tertiary_user_name` | Terceiro usuário |
| `user_3_name` | `fourth_user_name` | Quarto usuário (se existir) |
| `coHolder.name` | `co_holder_name` | Cotitular (só o 1º) |
| `coHolder.taxIdentification` | `co_holder_tax_id` | CPF/CNPJ do cotitular |

---

## 🧪 Como Testar

1. **Ative o ambiente virtual:**
   ```bash
   source venv/bin/activate  # ou o path correto do seu venv
   ```

2. **Execute o exemplo:**
   ```bash
   python examples/account_information_schema_usage.py
   ```

3. **Resultado esperado:**
   ```
   ✅ Raw JSON validated successfully!
      Account: 000123456
      Holder: José Antônio Silva
      Users count: 2

   1️⃣ Validated raw JSON for account 000123456
   2️⃣ Flattened users array
   3️⃣ Normalized with pandas
      Columns before rename: [...]
   4️⃣ Renamed columns
      Columns after rename: [...]
   5️⃣ ✅ Flattened data validated successfully!
      account_number: 000123456
      holder_name: José Antônio Silva
      primary_user_email: jose.antonio@email.com
      secondary_user_email: carlos.silva@email.com
   ```

---

## ⚠️ Observações Importantes

1. **CoHolders:** Até o momento (20/01/2026), a API do BTG envia apenas um Co Titular. (`co_holder_name`, `co_holder_tax_id`)
2. **Users:** Suporta até **4 usuários** (primary, secondary, tertiary, fourth)
3. **Campos Opcionais:** Todos os campos de usuários e cotitular são `Optional` no schema flat
4. **Tabela Parquet:** O schema `AccountInformationFlat` reflete exatamente o que é salvo em `database_tmp/accounts_users_info.parquet`

---

## 📁 Arquivos Relacionados

- Schema: `src/btg/schemas/account_information.py`
- Helpers: `src/util/helpers.py` (funções `_flat_users_key`, `create_list_users_info`)
- Transformação: `src/tmp/handles_data_transformation.py` (função `upsert_account_users_info_parquet`)
- Mapeamento: `src/app/settings.py` (constante `BTG_ACCOUNT_API_TO_STANDARD`)
- Exemplo: `examples/account_information_schema_usage.py`
