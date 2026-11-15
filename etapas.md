# Etapas do desenvolvimento

## Etapa 1 — Mapeamento e diagnóstico inicial

Data: 15/11/2026.

Objetivo: ler o README, examinar a estrutura do sistema e o estado do Git e executar os testes existentes, sem corrigir o código nesta etapa.

### Estrutura do sistema

O projeto é um CLI Python 3.11+ que lê reservas de hotel e taxas de câmbio em CSV e gera um relatório consolidado em JSON. O runtime utiliza apenas a biblioteca padrão do Python.

| Caminho | Responsabilidade |
| --- | --- |
| `README.md` | Regras de negócio, contrato do CLI, formato do relatório e requisitos de entrega. |
| `pyproject.toml` | Metadados do projeto e configuração do pytest e Ruff. |
| `requirements.txt` | Informa que não há dependências de runtime. |
| `requirements-dev.txt` | Dependências de desenvolvimento: pytest e Ruff. |
| `src/onfly_report/__main__.py` | Ponto de entrada de `python -m onfly_report`. |
| `src/onfly_report/cli.py` | Argumentos, execução da geração, tratamento de erros, gravação do JSON e resumo no stdout. |
| `src/onfly_report/models.py` | Modelos `RawRow` e `Reservation`. |
| `src/onfly_report/repositories/` | Leitura dos CSVs de reservas e taxas de câmbio. |
| `src/onfly_report/services/row_parser.py` | Conversão dos campos do CSV para os tipos de domínio. |
| `src/onfly_report/services/status_policy.py` | Definição dos status faturáveis. |
| `src/onfly_report/services/stay_calculator.py` | Cálculo das noites de quarto. |
| `src/onfly_report/services/currency_converter.py` | Conversão monetária para BRL. |
| `src/onfly_report/services/report_builder.py` | Orquestração, contagens, agregações, ranking e formatação do relatório. |
| `src/onfly_report/exceptions.py` e `logging_config.py` | Exceções de domínio e configuração de logs. |
| `data/` | Reservas, taxas de câmbio e amostra de validação. |
| `tests/` | Cinco testes que executam o CLI completo com arquivos temporários; utilitários em `helpers.py`. |
| `output/` | Destino dos relatórios gerados. |
| `entrega/` | Documentação da entrega; no diagnóstico inicial, continha apenas `.gitkeep`. |

Fluxo esperado pelo README: ler → converter tipos → contar status → filtrar somente `CONFIRMED` → agregar → serializar.

### Estado inicial do Git

- Branch: `main`.
- Commit observado: `5923685` — `chore: adiciona projeto original do desafio`.
- Sem commits à frente ou atrás da referência local `origin/main`; não foi feito fetch para verificar o servidor remoto.
- Sem alterações em arquivos rastreados.
- Arquivo não rastreado já existente: `tatus`.
- Nenhum arquivo do projeto foi editado durante o diagnóstico inicial.

### Execução dos testes

Comando utilizado:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
```

As opções `-B` e `-p no:cacheprovider` evitam a geração de bytecode e do cache do pytest. Os testes criam suas entradas e saídas em diretórios temporários.

A primeira tentativa, dentro do sandbox, não conseguiu acessar o Python base da `.venv` e retornou `No Python at ...`. A configuração do ambiente aponta para Python 3.11.9 no perfil do usuário. Após autorização para executar fora do sandbox, o mesmo comando iniciou o pytest normalmente. Portanto, o bloqueio inicial era de acesso ao ambiente, não uma falha confirmada da instalação do Python.

Resultado: **5 testes falharam em 1,38 s**, com código de saída `1`.

| Teste | Resultado observado | Resultado esperado | Diagnóstico |
| --- | --- | --- | --- |
| `test_currency_conversion_to_brl` | Total `118.45` | Total `642.00` | Conversão divide pela taxa em vez de multiplicar. |
| `test_nights_across_month_boundary` | `-28` noites | `3` noites | Cálculo subtrai apenas os dias do mês. |
| `test_regression_report_on_sample` | Total `1018.45`; média `203.69` | Total `1542.00`; média `308.40` | Erro de câmbio se propaga para total e média. |
| `test_status_rules_exclude_cancelled_and_no_show` | Total `120.00` | Total `100.00` | Reserva `NO_SHOW` é incluída como faturável. |
| `test_top_hotels_are_ranked_descending` | `H04, H03, H02` | `H01, H02, H03` | Ranking ordena valores de forma crescente. |

### Defeitos e inconsistências encontrados

1. **Operação cambial invertida.** Em `services/currency_converter.py:11`, o valor é dividido pela taxa. O contrato exige `amount * rate_to_brl`.
2. **Uso de ponto flutuante no dinheiro.** Na mesma função, valor e taxa são convertidos para `float` antes da operação. Isso viola a exigência de usar `Decimal` e pode introduzir imprecisão. A formatação final com half-up já existe, mas não elimina a perda de precisão anterior. Esse problema foi identificado por leitura do código, sem teste isolado fornecido para demonstrá-lo.
3. **Diferença de datas incorreta.** Em `services/stay_calculator.py:10`, a expressão `(checkout.day - checkin.day) * rooms` ignora mês e ano. Deve considerar a diferença completa entre as datas, não inclusiva, multiplicada pelos quartos.
4. **Filtro de status permissivo.** Em `services/status_policy.py:8`, qualquer status diferente de `CANCELLED` é considerado faturável. Isso inclui `NO_SHOW`, contrariando a regra de aceitar apenas `CONFIRMED`. Afeta noites, valores, agregação mensal e ranking; as contagens por status no teste estavam corretas.
5. **Ranking em ordem invertida.** Em `services/report_builder.py:91`, a ordenação usa valor crescente. O contrato exige valor decrescente e, nos empates, `hotel_id` crescente.
6. **Leitura truncada em 200 reservas.** Em `repositories/csv_reservation_repository.py:47–48`, há uma interrupção explícita ao atingir 200 registros. O CSV principal contém 300 reservas, portanto as últimas 100 são ignoradas. Afeta contagens e agregações. Esse defeito foi identificado por inspeção do código e contagem dos dados, sem cobertura nos cinco testes fornecidos.

### Situação ao encerrar a etapa

Diagnóstico concluído. Nenhuma correção foi aplicada ao código, aos testes ou aos dados. Este registro documenta a situação inicial e servirá de base para as próximas etapas.

## Etapa 2 — Correção da conversão cambial

Data: 15/11/2026.

Em `src/onfly_report/services/currency_converter.py`, a conversão passou a utilizar `amount * rate`, mantendo ambos os operandos como `Decimal`. Foram removidas as conversões para `float` e substituída a divisão pela multiplicação exigida pelo README. O resultado permanece sem arredondamento nessa função.

Validação executada com o Python da `.venv`, fora do sandbox para acessar o interpretador base:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/test_currency.py
```

Resultado: **1 teste passou em 0,32 s**, com código de saída `0`. O cenário de BRL 100,00 mais USD 100,00 à taxa de 5,42 agora totaliza corretamente `642.00` BRL. A suíte completa não foi executada nesta etapa; os demais defeitos identificados continuam pendentes. Os testes fornecidos permaneceram inalterados.

## Etapa 3 — Correção do cálculo de noites

Data: 15/11/2026.

Em `src/onfly_report/services/stay_calculator.py`, o cálculo passou de `(checkout.day - checkin.day) * rooms` para `(checkout - checkin).days * rooms`. A subtração agora considera as datas completas, incluindo mês e ano. O atributo `.days` extrai a quantidade de dias do intervalo resultante, que é multiplicada pelo número de quartos, mantendo a diferença não inclusiva.

Validação executada com o Python da `.venv`, fora do sandbox para acessar o interpretador base:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/test_nights.py
```

Resultado: **1 teste passou em 0,38 s**, com código de saída `0`. O cenário de check-in em 30/01/2025 e check-out em 02/02/2025, para um quarto, agora retorna corretamente `3` noites, em vez de `-28`. A suíte completa não foi executada nesta etapa. Os testes fornecidos permaneceram inalterados.
