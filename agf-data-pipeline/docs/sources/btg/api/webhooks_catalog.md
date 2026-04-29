# Webhooks / Relatórios – Catálogo

Este arquivo descreve os webhooks disponíveis, seus serviços e exemplos de payload/arquivo.

---

## Índice
1. Movimentações por Conta (`operations-by-account`)
2. Movimentações da Conta por Mercado e Ativo (`operations-by-market-and-asset`)
3. Movimentações por Parceiro (`operations-by-partner`)
4. Posições por Conta (`positions-by-account`)
5. Relacionamento de Conta por Assessor (`account-advisor`)
6. Relatório de Reservas de IPO (`ipo-report-reservation`)
7. Relatório de Push de IPO (`ipo-report-push`)
8. Relatório de Performance (`performance-report`)
9. Relatório de Informação de Candidatos (`partner-report-hub`)
10. Partner Report Títulos Públicos (`partner-report-government-bond`)
11. Partner Report Fixed Income (`partner-report-fixed-income`)
12. Partner Report Debêntures (`partner-report-debentures`)
13. Partner Report CRA/CRI (`partner-report-cra-cri`)
14. Partner Report Compromissadas (`partner-report-compromissadas`)
15. Relatório de TIR Mensal (`rm-reports-monthly-tir`)
16. Relatório de Dados Cadastrais (`rm-reports-registration-data`)
17. Relatório de Dados Onboarding (`rm-reports-onboarding-data`)
18. Relatório de Movimentação (`rm-reports-movement`)
19. Relatório de Fundos de Informação (`rm-reports-funds-information`)
20. Relatório de Fundos (`rm-reports-funds`)
21. Relatório de Fechamento de Movimentação Mensal (`rm-reports-monthly-movement`)
22. Relatório de Posição (`rm-reports-position`)
23. Relatório de Custódia Diário (`partner-report-custodia`)
24. Relatório de Custódia por Data de Referência (`partner-report-custodia-by-date`)
25. Informação Pública de Fundos por Parceiro (`funds-information-by-partner`)
26. Posições por Conta V2 (`positions-by-account-v2`)
27. Informações de Vínculo de Conta (`rm-reports-account-link`)
28. Relatório Base de Contas – Base BTG (`rm-reports-account-base`)
29. Informações de Representante Legal de Conta (`rm-reports-representative`)
30. Relatório de dados do STVM (`partner-report-stvm`)
31. Informações de Banking (`rm-reports-banking`)
32. Relatório de Fechamento de Comissão Mensal (`rm-reports-monthly-commission`)
33. Relatório de Open Finance – Consentimento (`rm-reports-consent-openfinance`)
34. Relatório de Open Finance (`rm-reports-openfinance`)
35. Relatório de Posição Gerencial por Data (`rm-reports-position-by-date`)
36. Relatório de Pagamento de Previdência (`rm-reports-pension-payment`)
37. Relatório de NNM Gerencial (`rm-reports-nnm`)
38. Relatório de Operações de Câmbio (`rm-reports-exchange-operation`)
39. Relatório de Extrato de Cartão de Crédito (`rm-reports-credit-card`)
40. Relatório de Fechamento de NNM Mensal (`rm-reports-monthly-nnm`)
41. Relatório de Operações (`rm-reports-operations`)
42. Relatório de Notas de Corretagem – Derivativos (`brokerage-notes-derivative`)
43. Posições por Parceiro (`positions-by-partner`)
44. Relatório de FEE Fixo (`rm-reports-fee-fixo`)
45. Relatório de Dados Cadastrais Clube e Fundos (`rm-reports-registration-data-club-funds`)
46. Notificação de Saída do STVM (`out-stvm-listener`)
47. Relatório de Principalidade (`rm-reports-principality`)
48. Relatório de Reserva de Fundo Fechado (`rm-reports-closed-fund-reserve`)
49. Account Movement Listener (`account-movement`)
50. Relatório de TIR Diário (`daily-profitability`)
51. Relatório de TIR Mensal por Cliente (`monthly-customer-profitability`)
52. Relatório de TIR Mensal de Produto (`monthly-product-profitability`)
53. Relatório de TIR Mensal por Estratégia (`monthly-strategy-profitability`)
54. Relatório de Pré‑Operações (`rm-reports-pre-operations`)
55. Relatório de Portabilidade de Previdência (`rm-reports-pension-portability`)
56. Relatório de Vínculo de Contas Fundos e Clube (`rm-reports-account-link-funds-club`)
57. Relatório de Alocação de Ativos (`rm-reports-asset-allocation`)
58. Recomendação de Operação (`rm-reports-trade-idea`)
59. Bloqueio Judicial (`rm-reports-judicial-block`)

---

## 1. Movimentações por Conta

- **ID:** 6  
- **Serviço:** `operations-by-account`  
- **Método:** POST  
- **Descrição curta:** Movimentações de uma conta  
- **System owner:** `iaas-operation-api`  
- **Content-Type:** `application/json`

**Descrição:**  
Webhook responsável por retornar todas as movimentações de uma conta. Necessário assinar o webhook `operations-by-account` e depois chamar os endpoints `get-movements-by-account-full`, `get-movements-by-account-monthly` ou `get-movements-by-account-weekly` na API de Movimentação.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"errors":[{"code":null,"message":null}],"response":{"accountNumber":"000123456","fileSize":12,"startDate":"2021-08-01","endDate":"2021-08-13","url":"https://invest-reports-dev.s3.amazonaws.com/iaas-aws-operation-api/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX","lastModified":"2025-02-19T00:40:15.000+00:00"}}
```
</details>

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"accountNumber":123456,"marketName":"TESTE","subMarketName":"SUB TESTE","interfaceDate":"02/12/1900 00:00","asset":"ASSET-00123","fundCnpj":123457000000,"movementDate":"02/12/1900 00:00","movementHistory":"COMPRA","launchType":"COMPRA","grossValue":123,"irValue":0,"iofValue":0,"quantity":99,"price":0.01,"brokerageFees":0.5,"optionType":"OPTION","exerciseDate":"02/12/1900 00:00","premium":"SIM","premiumValue":1,"dueDate":"07/01/1990 00:00","issueDate":"03/01/1900 00:00","index":"BTG","fee":0,"issuer":"BTG","accountingGroupCode":"GROUP","type":"F","assetCode":123456,"buyDate":"02/12/1900 00:00","stockOperation":"TESTE","settlementDate":"2023-04-11 00:00:00","description":"EXEMPLO","byeFee":0.1,"pensionType":"VGBL"}
```
</details>

---

## 2. Movimentações da Conta por Mercado e Ativo

- **ID:** 12  
- **Serviço:** `operations-by-market-and-asset`  
- **Método:** POST  
- **Descrição curta:** Buscar histórico de conta por Mercado e Ativo  
- **System owner:** `iaas-operation-api`  
- **Content-Type:** `application/json`

**Descrição:**  
Webhook responsável por retornar histórico de movimentações da conta por Mercado e Ativo. Necessário assinar o webhook `operations-by-market-and-asset` e depois chamar o endpoint `post-movements-by-market-and-asset` na API de Movimentação.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"errors":[{"code":null,"message":null}],"response":{"accountNumber":"000123456","fileSize":123,"startDate":"2021-05-01","endDate":"2022-06-20","url":"https://invest-reports-prd.s3.sa-east-1.amazonaws.com/iaas-aws-operation-api/12345678900011/000123456_20210501_20220620.zip?XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX","signedURLExpirationDate":"2022-07-20T21:28:13.543Z","lastModified":"2023-09-30T15:30:00Z"}}
```
</details>

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"accountNumber":123456,"marketName":"TESTE","subMarketName":"SUB TESTE","interfaceDate":"02/12/1900 00:00","asset":"ASSET-00123","fundCnpj":123457000000,"movementDate":"02/12/1900 00:00","movementHistory":"COMPRA","launchType":"COMPRA","grossValue":123,"irValue":0,"iofValue":0,"quantity":99,"price":0.01,"brokerageFees":0.5,"optionType":"OPTION","exerciseDate":"02/12/1900 00:00","premium":"SIM","premiumValue":1,"dueDate":"07/01/1990 00:00","issueDate":"03/01/1900 00:00","index":"BTG","fee":0,"issuer":"BTG","accountingGroupCode":"GROUP","type":"F","assetCode":123456,"buyDate":"02/12/1900 00:00","stockOperation":"TESTE","settlementDate":"2023-04-11 00:00:00","description":"EXEMPLO","byeFee":0.1,"pensionType":"VGBL"}
```
</details>

---

## 3. Movimentações por Parceiro

- **ID:** 13  
- **Serviço:** `operations-by-partner`  
- **Método:** POST  
- **Descrição curta:** Buscar todas as movimentações por Parceiro  
- **System owner:** `iaas-operation-api`  
- **Content-Type:** `application/json`

**Descrição:**  
Webhook responsável por retornar todas as movimentações de todas as contas do parceiro. Necessário assinar o webhook `operations-by-partner` e depois chamar os endpoints `post-movements-by-market-and-asset`, `post-movements-by-partner-and-period`, `get-movements-by-partner-monthly` ou `get-movements-by-partner-weekly` na API de Movimentação.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"errors":[{"code":null,"message":null}],"response":{"fileSize":12,"startDate":"2021-08-01","endDate":"2021-08-13","url":"https://invest-reports-dev.s3.amazonaws.com/iaas-aws-operation-api/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX","lastModified":"2025-02-19T00:40:15.000+00:00"}}
```
</details>

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"accountNumber":123456,"marketName":"TESTE","subMarketName":"SUB TESTE","interfaceDate":"02/12/1900 00:00","asset":"ASSET-00123","fundCnpj":123457000000,"movementDate":"02/12/1900 00:00","movementHistory":"COMPRA","launchType":"COMPRA","grossValue":123,"irValue":0,"iofValue":0,"quantity":99,"price":0.01,"brokerageFees":0.5,"optionType":"OPTION","exerciseDate":"02/12/1900 00:00","premium":"SIM","premiumValue":1,"dueDate":"07/01/1990 00:00","issueDate":"03/01/1900 00:00","index":"BTG","fee":0,"issuer":"BTG","accountingGroupCode":"GROUP","type":"F","assetCode":123456,"buyDate":"02/12/1900 00:00","stockOperation":"TESTE","settlementDate":"2023-04-11 00:00:00","description":"EXEMPLO","byeFee":0.1,"pensionType":"VGBL"}
```
</details>

---

## 4. Posições por Conta

- **ID:** 11  
- **Serviço:** `positions-by-account`  
- **Método:** POST  
- **Descrição curta:** Buscar histórico posição renda fixa de uma conta  
- **System owner:** `iaas-position-api`

**Descrição:**  
Webhook para busca de histórico de posição de renda fixa para uma conta. Necessário assinar o webhook `positions-by-account` e depois chamar os endpoints `post-position-unit-price-by-account` ou `get-position-history-unit-price-by-account` na API de Posição.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"errors":[{"code":null,"message":null}],"response":{"accountNumber":"000123456","fileSize":12,"startDate":"2021-08-01","endDate":"2021-08-13","url":"https://invest-reports-dev.s3.amazonaws.com/iaas-aws-position-api/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX","lastModified":"2023-09-30T15:30:00Z"}}
```
</details>

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"accountNumber":123456,"interfaceDate":"26/03/1900 00:00","marketName":"AA","subMarketName":"AA","asset":"Conta Corrente","movementHistory":"DEPOSITO EM C/C","quantity":0,"unitPrice":0,"irValue":0,"iofValue":0,"cost":0,"grossValue":0,"netValue":0,"acquisitionDate":"01/01/1900 00:00","purchaseFeeAmount":1,"assetCode":123}
```
</details>

---

## 5. Relacionamento de Conta por Assessor

- **ID:** 7  
- **Serviço:** `account-advisor`  
- **Método:** POST  
- **Descrição curta:** Receber os assessores com suas respectivas contas  
- **System owner:** `iaas-account-advisor-api`

**Descrição:**  
Webhook responsável por retornar os assessores com suas respectivas contas. Necessário assinar o webhook `account-advisor` e depois chamar o endpoint `get-accounts-by-advisor`.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"url":"https://invest-reports-prd.s3.sa-east-1.amazonaws.com/iaas-aws-account-advisor-api/XXXXXXXXXXXXXX/","fileSize":1234,"filters":{"cge":"123456","cnpj":"12345678000123","lastModified":"2023-09-30T15:30:00Z"}}
```
</details>

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"account":"001234567","bondDate":"2022-10-19T18:07:49Z","username":"José da Silva","login":"a0123456789","sgCGE":"3456789","officeCGE":"9876543","officeName":"BTG Pactual","officeDocument":"11111111111000"}
```
</details>

---

## 6. Relatório de Reservas de IPO

- **ID:** 8  
- **Serviço:** `ipo-report-reservation`  
- **Método:** POST  
- **Descrição curta:** Reservas de ofertas ativas  
- **System owner:** `iaas-ipo-report-api`

**Descrição:**  
Webhook responsável por retornar reservas de ofertas ativas de IPO. Necessário assinar `ipo-report-reservation` e chamar `post-ipo-reports-reservation`.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"errors":[{"code":null,"message":null}],"response":{"filter":{"accountNumber":"12345","distributionName":"NAME"},"pageable":{"page":0,"pageSize":10},"fileSize":10,"url":"https://invest-reports.s3.amazonaws.com/iaas-aws-ipo-report-api/reservation/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX","lastModified":"2023-09-30T15:30:00Z"}}
```
</details>

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"CONTA":123456,"NOME":"Fulano de Tal","NOME_DISTRIBUICAO":"FUNDO TESTE","SYMBOL":"PUBT00","MARKET_TYPE":"CORRETORA","MODALIDADE":"Compra de Ativo","LIMITE_OPERACIONAL":0,"DATA_ATUALIZACAO_LIMITE":"1900-01-12T06:30:29.528","VALOR_DESEJADO":0,"VALOR_POSSÍVEL":0,"PRECO_UNITARIO":0,"TAXA":1,"VINCULADO":"SIM","LIMITE_BLOQUEADO":"Limite Não Bloqueado","STATUS":"Limite Suficiente","PARTNER":"PARCEIRO DO BANCO","OFFICER":"BELTRANO","RESERVATION_END_DATE":"1900-03-14T16:00:00.000","BOUND_END_DATE":"1990-03-14T16:00:00.000"}
```
</details>

---

## 7. Relatório de Push de IPO

- **ID:** 9  
- **Serviço:** `ipo-report-push`  
- **Método:** POST  
- **Descrição curta:** Push de ofertas ativas  
- **System owner:** `iaas-ipo-report-api`

**Descrição:**  
Webhook responsável por retornar pushes de ofertas ativas de IPO. Necessário assinar `ipo-report-push` e chamar `post-ipo-reports-push`.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"errors":[{"code":null,"message":null}],"response":{"filter":{"accountNumber":"12345","distributionName":"NAME","operationType":"R"},"pageable":{"page":0,"pageSize":10},"fileSize":10,"url":"https://invest-reports.s3.amazonaws.com/iaas-aws-ipo-report-api/push/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX","lastModified":"2023-09-30T15:30:00Z"}}
```
</details>

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"CONTA":123456,"NOME":"Fulano de Tal","NOME_DISTRIBUICAO":"FUNDO TESTE","SYMBOL":"PUBT00","MARKET_TYPE":"CORRETORA","MODALIDADE":"Compra de Ativo","LIMITE_OPERACIONAL":0,"DATA_ATUALIZACAO_LIMITE":"1900-01-12T06:30:29.528","VALOR_DESEJADO":0,"VALOR_POSSÍVEL":0,"PRECO_UNITARIO":0,"TAXA":1,"VINCULADO":"SIM","LIMITE_BLOQUEADO":"Limite Não Bloqueado","STATUS":"Limite Suficiente","PARTNER":"PARCEIRO DO BANCO","OFFICER":"BELTRANO","RESERVATION_END_DATE":"1900-03-14T16:00:00.000","BOUND_END_DATE":"1990-03-14T16:00:00.000"}
```
</details>

---

## 8. Relatório de Performance

- **ID:** 1982  
- **Serviço:** `performance-report`  
- **Método:** POST  
- **Descrição curta:** Obter relatório de performance por conta  
- **System owner:** `iaas-profitability-api`

**Descrição:**  
Webhook responsável por retornar o relatório de performance da conta solicitada. Assinar `performance-report` e chamar `post-performance-report-by-account`.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"errors":[{"code":null,"message":null}],"response":{"fileSize":123,"startDate":"2024-05-01","endDate":"2024-06-20","url":"https://invest-reports-uat.s3.amazonaws.com/iaas-profitability-api/99999999999999/XXXXXXXXXXXXXXX","signedURLExpirationDate":"2024-08-04T21:28:13.543Z"}}
```
</details>

---

## 9. Relatório de Informação de Candidatos

- **ID:** 34  
- **Serviço:** `partner-report-hub`  
- **Método:** POST  
- **Descrição curta:** Busca relatório de informação de candidatos  
- **System owner:** `iaas-partner-report-hub-api`

**Descrição:**  
Webhook responsável por retornar relatório de informação de candidatos. Assinar `partner-report-hub` e chamar `get-report-onboarding-by-partner` ou `post-report-onboarding-by-partner-and-period`.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"errors":[{"code":null,"message":null}],"response":{"url":"https://invest-reports-prd.s3.sa-east-1.amazonaws.com/iaas-aws-partner-report-hub-api/XXXXXXXXXXXXXX/","fileSize":1234,"filters":{"cge":"123456","cnpj":"12345678000123"},"lastModified":"2023-09-30T15:30:00Z"}}
```
</details>

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"cod_file":"e705277d-8983-48a4-bc0a-94210f7c2039-2023-02-12-05","candidate_id":1234567,"name":"Maria José da Silva","email":"maria.jose01@gmail.com","cpf":11122233344}
```
</details>

---

## 10. Partner Report Títulos Públicos

- **ID:** 103  
- **Serviço:** `partner-report-government-bond`  
- **Método:** POST  
- **Descrição curta:** Busca relatório de Títulos públicos por parceiro  
- **System owner:** `iaas-partner-report-extractor-api`

**Descrição:**  
Webhook responsável pela busca de informações de Relatório de Títulos Públicos por Parceiro. Assinar `partner-report-government-bond` e chamar `get-partner-report-government-bond`.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"url":"https://invest-reports-prd.s3.sa-east-1.amazonaws.com/iaas-aws-partner-report-extractor-api/XXXXXXXXXXXXXX/","fileSize":1234,"filters":{"cge":"123456","cnpj":"12345678000123"},"lastModified":"2023-09-30T15:30:00Z"}
```
</details>

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"activeCode":"LFT","applicationDate":"2023-06-14T09:51:53.635-0300","productName":"LFT","puValue":"13322.63"}
```
</details>

---

## 11. Partner Report Fixed Income

- **ID:** 100  
- **Serviço:** `partner-report-fixed-income`  
- **Método:** POST  
- **Descrição curta:** Busca relatório de RF por parceiro  
- **System owner:** `iaas-partner-report-extractor-api`

**Descrição:**  
Webhook responsável pela busca de informações de Relatório de Renda Fixa por Parceiro. Assinar `partner-report-fixed-income` e chamar `get-partner-report-fixed-income`.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"url":"https://invest-reports-prd.s3.sa-east-1.amazonaws.com/iaas-aws-partner-report-extractor-api/XXXXXXXXXXXXXX/","fileSize":1234,"filters":{"cge":"123456","cnpj":"12345678000123"},"lastModified":"2023-09-30T15:30:00Z"}
```
</details>

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"productID":"123456","productName":"CDB","issuerName":"Banco BTG PACTUAL","indexCaptureName":"CDI","percentIndexValue":"10.0"}
```
</details>

---

## 12. Partner Report Debêntures

- **ID:** 102  
- **Serviço:** `partner-report-debentures`  
- **Método:** POST  
- **Descrição curta:** Busca relatório de Debêntures por parceiro  
- **System owner:** `iaas-partner-report-extractor-api`

**Descrição:**  
Webhook responsável pela busca de informações de Debêntures por Parceiro. Assinar `partner-report-debentures` e chamar `get-partner-report-debentures`.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"url":"https://invest-reports-prd.s3.sa-east-1.amazonaws.com/iaas-aws-partner-report-extractor-api/XXXXXXXXXXXXXX/","fileSize":1234,"filters":{"cge":"123456","cnpj":"12345678000123"},"lastModified":"2023-09-30T15:30:00Z"}
```
</details>

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"id":"123456","productName":"BTG123","activeCode":"BTG123","indexCaptureName":"IPCA","percentIndexValue":"5.9"}
```
</details>

---

## 13. Partner Report CRA/CRI

- **ID:** 101  
- **Serviço:** `partner-report-cra-cri`  
- **Método:** POST  
- **Descrição curta:** Busca relatório de CRA-CRI por parceiro  
- **System owner:** `iaas-partner-report-extractor-api`

**Descrição:**  
Webhook responsável pela busca de informações de CRA/CRI por Parceiro. Assinar `partner-report-cra-cri` e chamar `get-partner-report-cra-cri`.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"url":"https://invest-reports-prd.s3.sa-east-1.amazonaws.com/iaas-aws-partner-report-extractor-api/XXXXXXXXXXXXXX/","fileSize":1234,"filters":{"cge":"123456","cnpj":"12345678000123"},"lastModified":"2023-09-30T15:30:00Z"}
```
</details>

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"id":"123456","productName":"CRA202312Y","activeCode":"CRA020236Y","indexCaptureName":"IPCA","percentIndexValue":0.91}
```
</details>

---

## 14. Partner Report Compromissadas

- **ID:** 104  
- **Serviço:** `partner-report-compromissadas`  
- **Método:** POST  
- **Descrição curta:** Busca relatório de Compromissadas por parceiro  
- **System owner:** `iaas-partner-report-extractor-api`

**Descrição:**  
Webhook responsável pela busca de informações de Compromissadas. Assinar `partner-report-compromissadas` e chamar `get-partner-report-compromissadas`.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"url":"https://invest-reports-prd.s3.sa-east-1.amazonaws.com/iaas-aws-partner-report-extractor-api/XXXXXXXXXXXXXX/","fileSize":1234,"filters":{"cge":"123456","cnpj":"12345678000123"},"lastModified":"2023-09-30T15:30:00Z"}
```
</details>

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"id":"201","productName":"COMPRO TESTE","issuerName":"BANCO BTG PACTUAL S/A","taxValue":0.01}
```
</details>

---

## 15. Relatório de TIR Mensal

- **ID:** 133  
- **Serviço:** `rm-reports-monthly-tir`  
- **Método:** POST  
- **Descrição curta:** Obter o relatório de TIR mensal por parceiro  
- **System owner:** `iaas-rm-reports-api`

**Descrição:**  
Relatório de TIR mensal por parceiro. Assinar `rm-reports-monthly-tir` e chamar `get-rm-reports-monthly-tir`.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"errors":[{"code":null,"message":null}],"response":{"fileSize":123,"startDate":"2021-05-01","endDate":"2022-06-20","url":"https://invest-reports-uat.s3.amazonaws.com/iaas-aws-rm-reports-api/99999999999999/XXXXXXXXXXXXXXX","signedURLExpirationDate":"2022-10-13T21:28:13.543Z","lastModified":"2023-09-30T15:30:00Z"}}
```
</details>

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"012345678","dt_interface":"0.012344","vl_acumulado_mes":"0.012345","lucro_prejuizo":"0.012345"}
```
</details>

---

## 16. Relatório de Dados Cadastrais

- **ID:** 136  
- **Serviço:** `rm-reports-registration-data`  
- **Método:** POST  
- **Descrição curta:** Obter o relatório de dados cadastrais por parceiro  

**Descrição:**  
Assinar `rm-reports-registration-data` e chamar `get-rm-reports-registration-data`.

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"012345678","nome_completo":"José Maria","dt_nascimento":"1990-06-08","profissao":"EMPRESÁRIO (A)"}
```
</details>

---

## 17. Relatório de Dados Onboarding

- **ID:** 135  
- **Serviço:** `rm-reports-onboarding-data`  
- **Método:** POST  
- **Descrição curta:** Obter o relatório de dados onboarding por parceiro  

**Descrição:**  
Assinar `rm-reports-onboarding-data` e chamar `get-rm-reports-onboarding-data`.

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"012345678","vl_moveis":"10000.99","vl_imoveis":"10000.10","vl_investimentos":"10000.10"}
```
</details>

---

## 18. Relatório de Movimentação

- **ID:** 137  
- **Serviço:** `rm-reports-movement`  
- **Método:** POST  
- **Descrição curta:** Obter o relatório de movimentação por parceiro  

**Descrição:**  
Assinar `rm-reports-movement` e chamar `get-rm-reports-movement`.

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"012345678","dt_interface":"2023-06-07","dt_movimentacao":"2023-06-08","mercado":"CONTA CORRENTE","historico_movimentacao":"IR MP206 - OPCAO DAY TRADE"}
```
</details>

---

## 19. Relatório de Fundos de Informação

- **ID:** 232  
- **Serviço:** `rm-reports-funds-information`  
- **Método:** POST  
- **Descrição curta:** Busca relatório gerencial de Catálogo de Fundos  

**Descrição:**  
Assinar `rm-reports-funds-information` e chamar `get-rm-reports-funds-information`.

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nm_administrador":"BTG Pactual","nm_fundo":"BTG Acccess","nm_anbid_tipo":"Ações Livre","nm_indice_benchmark":"CDI"}
```
</details>

---

## 20. Relatório de Fundos

- **ID:** 233  
- **Serviço:** `rm-reports-funds`  
- **Método:** POST  
- **Descrição curta:** Obter o relatório de fundos por parceiro  

**Descrição:**  
Assinar `rm-reports-funds` e chamar `get-rm-reports-funds`.

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nm_administrador":"BTG Pactual","nm_fundo":"BTG Acccess","nm_gestor":"BTG Pactual","nr_cnpj":"012345"}
```
</details>

---

## 21. Relatório de Fechamento de Movimentação Mensal

- **ID:** 265  
- **Serviço:** `rm-reports-monthly-movement`  
- **Método:** POST  
- **Descrição curta:** Obter relatório de movimentação mensal p/ parceiro

**Descrição:**  
Assinar `rm-reports-monthly-movement` e chamar `get-rm-reports-monthly-movement`.

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"012345678","dt_interface":"2023-06-07","dt_movimentacao":"2023-06-08","mercado":"CONTA CORRENTE"}
```
</details>

---

## 22. Relatório de Posição

- **ID:** 628  
- **Serviço:** `rm-reports-position`  
- **Método:** POST  
- **Descrição curta:** Obter o relatório de posição por parceiro

**Descrição:**  
Assinar `rm-reports-position` e chamar `get-rm-reports-position`.

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"012345678","produto":"IBOVESPA MINI FUTURO AGO2023","ativo":"WINQ23","quantidade":10,"vl_custo":10.6}
```
</details>

---

## 23. Relatório de Custódia Diário (dia atual)

- **ID:** 199  
- **Serviço:** `partner-report-custodia`  
- **Método:** POST  
- **Descrição curta:** Relatório de Custódia Diário do dia Atual

**Descrição:**  
Assinar `partner-report-custodia` e chamar `get-partner-report-custody`.

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"accountNumber":"000000","accountName":"TESTE S/A","referenceDate":"10/04/2023","referenceAsset":"XXA11","qtdeAtual":"2500"}
```
</details>

---

## 24. Relatório de Custódia por Data de Referência

- **ID:** 200  
- **Serviço:** `partner-report-custodia-by-date`  
- **Método:** POST  
- **Descrição curta:** Relatório de Custódia por data de referência  

**Descrição:**  
Assinar `partner-report-custodia-by-date` e chamar `post-partner-report-custody-by-date`.

(Exemplo de arquivo igual ao item anterior.)

---

## 25. Informação Pública de Fundos por Parceiro

- **ID:** 1981  
- **Serviço:** `funds-information-by-partner`  
- **Método:** POST  
- **Descrição curta:** Busca catálogo público de Fundos por parceiro  

**Descrição:**  
Assinar `funds-information-by-partner` e chamar `get-public-funds-by-partner`.

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"name":"NOME FUNDO","cnpj":"1234567800091","isin":"BTG123456789","currency":"BRL","categoryCvm":"Multimercados"}
```
</details>

---

## 26. Posições por Conta V2

- **ID:** 694  
- **Serviço:** `positions-by-account-v2`  
- **Método:** POST  
- **Descrição curta:** Buscar histórico posição renda fixa de uma conta  

**Descrição:**  
Assinar `positions-by-account-v2` e chamar `post-position-unit-price-by-account-v2` ou `get-position-history-unit-price-by-account-v2`.

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"accountNumber":"123456","interfaceDate":"02/01/2014","marketName":"RF","asset":"DPGE-DPGE12001FN","quantity":"1000"}
```
</details>

---

## 27. Informações de Vínculo de Conta

- **ID:** 859  
- **Serviço:** `rm-reports-account-link`  
- **Método:** POST  
- **Descrição curta:** Obter Informações de Vínculo das contas

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"012345678","nm_officer":"Joao Maria das Neves","login":"jneves","cge_partner":"001234567"}
```
</details>

---

## 28. Relatório Base de Contas – Base BTG

- **ID:** 860  
- **Serviço:** `rm-reports-account-base`  
- **Método:** POST  
- **Descrição curta:** Relatórios das informações de contas - Base BTG.

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"001122335","nome_completo":"JOAO DE ABREU","nm_assessor":"Marcus Rocha","pl_total":"235422,03"}
```
</details>

---

## 29. Informações de Representante Legal de Conta

- **ID:** 826  
- **Serviço:** `rm-reports-representative`  
- **Método:** POST  
- **Descrição curta:** Obter Informações de Representante Legal

<details>
<summary>Exemplo de arquivo (fileExample)</summary>
OBS: Exemplo na documentação do BTG esta faltando alguns campos do que é retornado.

```json
{"nr_conta":"123456","nome_representante":"Maria João","cpf_representante":"11122233344","tipo_representante":"COMUM"}
```

Atualmente o retorno possui os campos abaixo:

```json
{"nr_conta": 1011889,
 "nome_representante": "JOELMA CALLYPSO",
 "cpf_representante": 11551671230,
 "celular": 5591988997788,
 "email": "jcallypso@hotmail.com",
 "idade": 54,
 "dt_nascimento": "02/02/1971",
 "perfil": "Completo",
 "tipo_representante": "COMUM",
 "flag_menor": "NÃO"}
```


</details>

---

## 30. Relatório de dados do STVM

- **ID:** 430  
- **Serviço:** `partner-report-stvm`  
- **Método:** POST  
- **Descrição curta:** Obter dados de STVM por parceiro.  

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"cod_carteira":"001234567","segment_digital":"B2B","tipo_lancamento":"Portabilidade de Entrada","valor_bruto":6873.81}
```
</details>

---

## 31. Informações de Banking

- **ID:** 563  
- **Serviço:** `rm-reports-banking`  
- **Método:** POST  
- **Descrição curta:** Obter informações de banking por parceiro

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"12345678","nome_cliente":"João Maria","tipo_conta":"Conta Corrente","auc_total":758233.03}
```
</details>

---

## 32. Relatório de Fechamento de Comissão Mensal

- **ID:** 1354  
- **Serviço:** `rm-reports-monthly-commission`  
- **Método:** POST  
- **Descrição curta:** Obter o relatório de Fechamento de Comissão Mensal

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"012345678","categoria":"RENDA VARIAVEL","produto":"Aluguel","vl_receita":"1.15"}
```
</details>

---

## 33. Relatório de Open Finance – Consentimento

- **ID:** 1124  
- **Serviço:** `rm-reports-consent-openfinance`  
- **Método:** POST  
- **Descrição curta:** Open Finance - Consentimento

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"hash_id":"12345678","nr_conta":"Nubank","tipo_consentimento":"Renda Fixa","dt_fim_consentimento":"2024-07-30"}
```
</details>

---

## 34. Relatório de Open Finance

- **ID:** 1123  
- **Serviço:** `rm-reports-openfinance`  
- **Método:** POST  
- **Descrição curta:** Obter o relatório de Open Finance.

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"012345678","instituicao_origem":"Nubank","produto":"CDB","taxa":1.02}
```
</details>

---

## 35. Relatório de Posição Gerencial por Data

- **ID:** 1364  
- **Serviço:** `rm-reports-position-by-date`  
- **Método:** POST  
- **Descrição curta:** Obter Relatório de Posição por data

(Exemplo de arquivo igual ao relatório de posição.)

---

## 36. Relatório de Pagamento de Previdência

- **ID:** 1420  
- **Serviço:** `rm-reports-pension-payment`  
- **Método:** POST  
- **Descrição curta:** Pagamentos de previdência do escritório

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nosso_numero":"3798175","dt_emissao":"2024-12-01","valor":"2345.67","metodo_pagamento":"Débito em conta"}
```
</details>

---

## 37. Relatório de NNM Gerencial

- **ID:** 1255  
- **Serviço:** `rm-reports-nnm`  
- **Método:** POST  
- **Descrição curta:** Obter o relatório de NNM Gerencial.

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"001234567","dt_captacao":"2024-09-30","ativo":"BTG11","captacao":"2233.44"}
```
</details>

---

## 38. Relatório de Operações de Câmbio

- **ID:** 1288  
- **Serviço:** `rm-reports-exchange-operation`  
- **Método:** POST  

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"tipo_lancamento":"Remessa","dt_operacao":"2024-07-30","moeda":"USD","vl_ext":2200.0}
```
</details>

---

## 39. Relatório de Extrato de Cartão de Crédito

- **ID:** 1321  
- **Serviço:** `rm-reports-credit-card`  
- **Método:** POST  

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"001122334","tp_cartao":"VIRTUAL","limite_disponivel":2456.83,"data_fechamento_fatura":"2025-01-08"}
```
</details>

---

## 40. Relatório de Fechamento de NNM Mensal

- **ID:** 1363  
- **Serviço:** `rm-reports-monthly-nnm`  
- **Método:** POST  

(Exemplo de arquivo igual ao NNM gerencial.)

---

## 41. Relatório de Operações

- **ID:** 1453  
- **Serviço:** `rm-reports-operations`  
- **Método:** POST  

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"009999999","nm_produto":"Porto DI CrPr FIRef","tipo_movimentacao":"Resgate","vl_liquido":"830"}
```
</details>

---

## 42. Relatório de Notas de Corretagem – Derivativos

- **ID:** 1486  
- **Serviço:** `brokerage-notes-derivative`  
- **Método:** POST  

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"exemple":null}
```
</details>

---

## 43. Posições por Parceiro

- **ID:** 1519  
- **Serviço:** `positions-by-partner`  
- **Método:** POST  
- **Descrição curta:** Obter arquivos de posições por parceiro

---

## 44. Relatório de FEE Fixo

- **ID:** 1585  
- **Serviço:** `rm-reports-fee-fixo`

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"009999999","taxa_especifica_conta":64.6,"tabela_taxas":[{"fee":1,"startValue":0}]}
```
</details>

---

## 45. Relatório de Dados Cadastrais Clube e Fundos

- **ID:** 1651  
- **Serviço:** `rm-reports-registration-data-club-funds`

(Exemplo de arquivo igual ao de dados cadastrais.)

---

## 46. Notificação de Saída do STVM

- **ID:** 925  
- **Serviço:** `out-stvm-listener`

<details>
<summary>Exemplo de payload / arquivo</summary>

```json
{"idDocumento":"001122","dataAtualizacao":"2023-05-10T22:41:29.693Z","status":{"name":"Pendente Validação","code":"P"},"account":{"accountNumber":"000123456"}}
```
</details>

---

## 47. Relatório de Principalidade

- **ID:** 1717  
- **Serviço:** `rm-reports-principality`

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"012345678","cliente_principal_conta":"Sim","pontuacao_total":8,"dt_referencia":"2025-05-01"}
```
</details>

---

## 48. Relatório de Reserva de Fundo Fechado

- **ID:** 1750  
- **Serviço:** `rm-reports-closed-fund-reserve`

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"012345678","cod_oferta":312,"vl_oferta":20000.30,"status_reserva":"Reserva Aprovada"}
```
</details>

---

## 49. Account Movement Listener

- **ID:** 397  
- **Serviço:** `account-movement`

**Descrição:**  
Notificação de Cash-event nas contas vinculadas ao escritório.

<details>
<summary>Exemplo de payload (body)</summary>

```json
{"type":"CASH_EVENT","data":{"value":18.06,"type":"CREDIT","createdAt":"2025-05-12T21:08:32.2661026Z","description":"RECEBIMENTO TRANSFERÊNCIA"},"accountNumber":"001234567"}
```
</details>

---

## 50. Relatório de TIR Diário

- **ID:** 1783  
- **Serviço:** `daily-profitability`

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"cod_carteira":"001234567","reference_date":"2023-03-20","auc":32540.13,"profitability_daily":0.0004095}
```
</details>

---

## 51. Relatório de TIR Mensal por Cliente

- **ID:** 1784  
- **Serviço:** `monthly-customer-profitability`

(Arquivo de exemplo enorme; mantido no JSON original.)

---

## 52. Relatório de TIR Mensal de Produto

- **ID:** 1785  
- **Serviço:** `monthly-product-profitability`

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"cod_carteira":"001234567","reference_month":"9/1/2023","product_id":111111111,"product_name":"PRODUCT NAME","profitability_mtd":0.012345678}
```
</details>

---

## 53. Relatório de TIR Mensal por Estratégia

- **ID:** 1786  
- **Serviço:** `monthly-strategy-profitability`

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"cod_carteira":"001234567","asset_allocation_strategy":"Renda Variável","reference_month":"9/1/2023","profitability_mtd":0.012345678}
```
</details>

---

## 54. Relatório de Pré‑Operações

- **ID:** 1787  
- **Serviço:** `rm-reports-pre-operations`

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"id_pre_operacao":11192299,"nr_conta":"012345678","tipo_operacao":"Aplicação","status":"Pendente de aprovação"}
```
</details>

---

## 55. Relatório de Portabilidade de Previdência

- **ID:** 1816  
- **Serviço:** `rm-reports-pension-portability`

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"dt_solicitacao":"2025-07-11","nr_conta":"012345678","tipo_portabilidade":"Entrada","vl_operacao":25000}
```
</details>

---

## 56. Relatório de Vínculo de Contas Fundos e Clube

- **ID:** 1849  
- **Serviço:** `rm-reports-account-link-funds-club`

(Exemplo de arquivo igual ao de vínculo de contas.)

---

## 57. Relatório de Alocação de Ativos

- **ID:** 1850  
- **Serviço:** `rm-reports-asset-allocation`

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"001644117","total_fin":3232640.78,"renda_variavel_allocation":0.45,"dt_referencia":"2025-08-25"}
```
</details>

---

## 58. Recomendação de Operação

- **ID:** 1882  
- **Serviço:** `rm-reports-trade-idea`

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"001644117","tipo":"CRA, CRI","ativo":"CRA0250018O","taxa_compra":5.95,"agio_desagio":"Deságio"}
```
</details>

---

## 59. Bloqueio Judicial

- **ID:** 1916  
- **Serviço:** `rm-reports-judicial-block`

<details>
<summary>Exemplo de arquivo (fileExample)</summary>

```json
{"nr_conta":"009999999","processo":"50800137220198210001","origem":"BACENJUD2","ativo":"CDB-CDB323JZBHY 12/Aug/2024","quantidade":290,"valor":2500.78}
```
</details>
