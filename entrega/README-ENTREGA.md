# Entrega — Consolidador de reservas de hotel

## Investigação e abordagem

O trabalho começou pela interpretação das regras do README, mapeamento dos componentes e execução dos cinco testes fornecidos, que falharam no estado original. As correções foram realizadas de forma incremental, com apoio do Codex. Revisão do código/diff, testes, registro gradual em `etapas.md` fora realizadas por mim, orientando o codex gradualmente durante a sessão. O versionamento foi realizado manualmente, via bash.

Após as correções, foram adicionados testes complementares para regras não cobertas pela suíte inicial. O histórico detalhado está em [etapas.md](etapas.md), e a declaração de participação está em [uso-de-ia/declaracao.md](uso-de-ia/declaracao.md).

## Defeitos corrigidos e causas raiz

| Defeito | Causa raiz | Correção |
| --- | --- | --- |
| Conversão cambial incorreta | O conversor dividia o valor pela taxa para BRL em vez de multiplicá-lo. | Utilização de `amount * rate`. |
| Perda de precisão monetária | O conversor transformava valor e taxa em `float` antes de calcular. | Operações mantidas em `Decimal`, com arredondamento apenas na serialização. |
| Noites incorretas na mudança de mês/ano | O cálculo subtraía os números dos dias do mês, ignorando as datas completas. | Utilização de `(checkout - checkin).days * rooms`. |
| Inclusão indevida de no-show | A política aceitava qualquer status diferente de `CANCELLED`. | Aceitação exclusiva de `CONFIRMED` para noites, valores e agregações. |
| Ranking invertido | A ordenação priorizava os menores valores. | Chave `(-amount, hotel_id)`, com valor decrescente e ID crescente nos empates. |
| Leitura incompleta | Um `break` encerrava a leitura após 200 reservas. | Remoção do limite, permitindo ler todas as 300 reservas da base. |

O contrato do CLI e o schema do relatório foram preservados. Os testes fornecidos e os arquivos `data/reservas_hoteis.csv` e `data/taxas_cambio.csv` permaneceram inalterados, conforme comparação com o material original.

## Como validar

Requisito: Python 3.11 ou superior. Execute os comandos na raiz do projeto.

### Windows — Git Bash

```bash
py -3.11 -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

### Linux/macOS — Bash

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

### Gerar os relatórios — Bash/Git Bash

Com o ambiente virtual ativado:

```bash
PYTHONPATH=src python -m onfly_report \
  --input data/reservas_hoteis.csv \
  --rates data/taxas_cambio.csv \
  --output output/report.json

PYTHONPATH=src python -m onfly_report \
  --input data/exemplo-validacao.csv \
  --rates data/taxas_cambio.csv \
  --output output/exemplo.json
```

O CLI cria o diretório de saída. Os arquivos gerados em `output/` são ignorados pelo Git e podem ser reproduzidos com esses comandos.

## Resultados

- Estado inicial: **5 testes falharam**.
- Estado final: **23 testes passaram**, sendo 5 fornecidos e 18 casos adicionais em `tests/test_readme_contract.py`.
- Execução documentada no ambiente Windows/Python 3.11: **23 passed in 8.01s**.
- Revisão independente da cópia enviada, com Python 3.12.14: **23 passed in 1.00s**. Os tempos variam conforme o ambiente.

| Base | Reservas | Confirmadas | Canceladas | No-show | Noites de quarto | Total BRL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Principal | 300 | 235 | 31 | 34 | 1347 | 396170.00 |
| Amostra do README | 12 | 9 | 2 | 1 | 28 | 7566.00 |

Na amostra, a diária média é `270.21`. Resumo, meses e ranking foram comparados integralmente aos resultados esperados do README.

Os testes complementares cobrem a base completa, desempate e limite do ranking, precisão e arredondamento half-up, virada de ano, múltiplos quartos, mês do check-in, ausência de reservas faturáveis, schema, offset de geração, argumentos inválidos, entradas inválidas, saída padrão e falha de escrita.

## Uso de IA

Houve uso de Codex no VS Code para diagnóstico, implementação dirigida, testes e documentação incremental. A divisão de responsabilidades está em `uso-de-ia/declaracao.md`.
