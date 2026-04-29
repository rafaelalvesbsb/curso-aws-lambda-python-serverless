# 🧪 Guia de Testes - AGFI Data Pipeline

## 📦 Instalação de Dependências

```bash
# Instalar dependências de desenvolvimento
uv pip install -e ".[dev]"

# Ou com pip
pip install -e ".[dev]"
```

## 🚀 Executando os Testes

### Todos os testes
```bash
pytest
```

### Apenas testes unitários (sem dependências externas)
```bash
pytest -m unit
```

### Apenas testes de integração (requerem credenciais reais)
```bash
pytest -m integration
```

### Teste específico
```bash
pytest tests/btg/test_btg_client_integration.py -v
```

### Com cobertura de código
```bash
pytest --cov=src --cov-report=html --cov-report=term
```

### Modo verboso
```bash
pytest -v
```

### Parar no primeiro erro
```bash
pytest -x
```

## 📋 Estrutura de Testes

```
tests/
├── conftest.py                          # Configurações compartilhadas
├── btg/
│   ├── __init__.py
│   └── test_btg_client_integration.py   # Testes do BTGClient
├── core/
│   └── __init__.py
├── hubspot/
│   └── __init__.py
└── aws/
    └── __init__.py
```

## 🏷️ Markers

- `@pytest.mark.unit` - Testes unitários (rápidos, sem dependências externas)
- `@pytest.mark.integration` - Testes de integração (requerem serviços reais)
- `@pytest.mark.slow` - Testes lentos (podem ser excluídos com `-m "not slow"`)

## 🔑 Testes de Integração BTG

Os testes de integração do BTGClient requerem credenciais reais:

```bash
# Configurar credenciais
export BTG_CLIENT_ID="seu_client_id"
export BTG_CLIENT_SECRET="seu_client_secret"

# Rodar testes de integração
pytest -m integration tests/btg/test_btg_client_integration.py -v
```

## ✅ O que os testes cobrem

### `test_btg_client_integration.py`

#### Testes Unitários:
- ✅ Função `_is_transient()` identifica erros transitórios corretamente
- ✅ Inicialização com variáveis de ambiente
- ✅ Inicialização com credenciais explícitas
- ✅ Falha na inicialização sem credenciais
- ✅ Geração de header Basic Auth
- ✅ Autenticação OAuth2 bem-sucedida
- ✅ Tratamento de erro quando `access_token` está faltando
- ✅ Tratamento de erro HTTP 401
- ✅ Chamada API bem-sucedida
- ✅ Tratamento de rate limit (429)
- ✅ Retry automático em erros 5xx
- ✅ Retry automático em 404 "Relatório não disponível"
- ✅ Endpoints individuais (account_base, position, open_finance)
- ✅ Health check (sucesso e falha)
- ✅ Context manager (async with)

#### Testes de Integração (requerem credenciais):
- ✅ Autenticação real com API BTG
- ✅ Health check com API real

## 📊 Cobertura de Código

Após rodar `pytest --cov=src --cov-report=html`, abra o relatório:

```bash
open htmlcov/index.html
```

## 🐛 Debug

### Ver logs detalhados
```bash
pytest -v -s
```

### Usar pdb para debug
```bash
pytest --pdb
```

### Debug no primeiro erro
```bash
pytest --pdb -x
```

## 🎯 Exemplos de Uso

### Rodar apenas testes do BTGClient
```bash
pytest tests/btg/ -v
```

### Rodar com output colorido
```bash
pytest --color=yes
```

### Rodar em paralelo (requer pytest-xdist)
```bash
pip install pytest-xdist
pytest -n auto
```

## ⚠️ Notas Importantes

1. **Testes de integração**: Requerem credenciais BTG válidas e conexão com internet
2. **Rate limiting**: Testes de integração podem ser afetados por rate limits da API
3. **Tempo de execução**: Testes de integração são mais lentos (~5-10s cada)
4. **Mocks**: Testes unitários usam mocks e não fazem chamadas reais

## 🔄 CI/CD

Para integração contínua, rode apenas testes unitários:

```bash
# No CI/CD pipeline
pytest -m "not integration" --cov=src --cov-report=xml
```

## 📝 Escrevendo Novos Testes

### Template de teste unitário:
```python
import pytest
from src.btg.client import BTGClient

@pytest.mark.unit
def test_my_feature():
    """Test description."""
    # Arrange
    client = BTGClient()

    # Act
    result = client.my_method()

    # Assert
    assert result == expected
```

### Template de teste de integração:
```python
import pytest
import os

@pytest.mark.skipif(
    not os.getenv("BTG_CLIENT_ID"),
    reason="BTG credentials not available"
)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_api():
    """Test with real API."""
    async with BTGClient() as client:
        result = await client.some_method()
        assert result is not None
```

## 🆘 Troubleshooting

### Erro: "ModuleNotFoundError: No module named 'src'"
```bash
# Instalar o pacote em modo editável
pip install -e .
```

### Erro: "pytest: command not found"
```bash
# Instalar dependências de dev
pip install -e ".[dev]"
```

### Testes muito lentos
```bash
# Rodar apenas testes rápidos
pytest -m "not slow" -m "not integration"
```
