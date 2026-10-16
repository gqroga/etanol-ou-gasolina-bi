# Guia de montagem do dashboard (Power BI Desktop)

O Power BI Desktop só roda no Windows, então o `.pbix` é montado lá seguindo este guia.
Tudo que é "código" (DAX, tema, consultas) já está pronto neste repositório. O trabalho manual é conectar, colar e arrastar os campos.

Tempo estimado: **1h30 a 2h**.

Arquivos de apoio:
- [`medidas.dax`](medidas.dax): todas as medidas, prontas para colar.
- [`tema_combustiveis.json`](tema_combustiveis.json): tema com a mesma paleta dos gráficos do notebook.
- [`../docs/kpis_referencia.csv`](../docs/kpis_referencia.csv): valores que o dashboard **precisa** reproduzir (gerado pelo notebook).

**Por que modo Import (e não DirectQuery):** desempenho ao navegar no relatório, sem depender do banco estar acessível
na hora, e suporte completo a DAX e inteligência de tempo. O Power Query só faz tipagem: nenhuma regra de limpeza fica aqui.

---

## 1. Conectar ao Postgres

O banco roda no Docker da máquina Linux. Para o Windows enxergá-lo:

1. Na máquina Linux, descubra o IP com `hostname -I` (ex.: `192.168.0.15`). O container já publica a porta 5432.
2. No Power BI: **Obter dados → Banco de dados PostgreSQL**.
   - Servidor: `192.168.0.15:5432` · Banco: `dw_combustiveis` · Modo: **Importar**.
   - Credencial (aba *Banco de dados*): usuário `bi_reader`, senha `BI_PASSWORD` do `.env`.
   - Se pedir o driver Npgsql, instale a versão indicada pela mensagem e reinicie o Power BI.
3. No navegador, marque **só as views do schema `mart`**:

| View | Renomear no Power BI para |
|---|---|
| `mart.vw_fato_preco` | `fPreco` |
| `mart.vw_dim_data` | `dData` |
| `mart.vw_dim_localidade` | `dLocalidade` |
| `mart.vw_dim_revenda` | `dRevenda` |
| `mart.vw_dim_produto` | `dProduto` |
| `mart.vw_dim_bandeira` | `dBandeira` |

> As views `vw_preco_mensal_uf` e `vw_paridade_mensal_uf` são para o notebook. **Não importe**: o Power BI calcula isso via DAX.

**Power Query:** só tipagem (ex.: `valor_venda` como *Número decimal*, `data` como *Data*). **Nenhuma** regra de limpeza aqui.

**Plano B (sem rede entre as máquinas):** exporte as views para CSV na máquina Linux e importe os CSVs:
```bash
for v in vw_fato_preco vw_dim_data vw_dim_localidade vw_dim_revenda vw_dim_produto vw_dim_bandeira; do
  docker exec dw_combustiveis psql -U postgres -d dw_combustiveis -c "\copy (SELECT * FROM mart.$v) TO STDOUT CSV HEADER" > $v.csv
done
```

## 2. Modelo

1. **Exibição de modelo:** crie as relações de 1 para muitos, filtro em **direção única** (dimensão → fato):
   - `dData[sk_data]` → `fPreco[sk_data]`
   - `dLocalidade[sk_localidade]` → `fPreco[sk_localidade]`
   - `dRevenda[sk_revenda]` → `fPreco[sk_revenda]`
   - `dProduto[sk_produto]` → `fPreco[sk_produto]`
   - `dBandeira[sk_bandeira]` → `fPreco[sk_bandeira]`
2. `dData` → **Marcar como tabela de datas** → coluna `data`.
3. `dData[nome_mes]` → *Classificar por coluna* `mes`. `dData[ano_mes]` → *Classificar por coluna* `ano_mes_ordem`.
4. Hierarquia em `dLocalidade`: **Região → UF → Município** (`regiao_nome`, `uf_sigla`, `municipio`).
5. Oculte as colunas `sk_*` e `fl_outlier` da fato (o usuário final não deve arrastá-las).
6. `dLocalidade[uf_sigla]` → *Categoria de dados* **Estado ou província** (para o mapa).

## 3. Medidas

1. **Página inicial → Inserir dados** → crie uma tabela vazia chamada `_Medidas`.
2. Para cada medida de [`medidas.dax`](medidas.dax): *Nova medida* → cole (nome = texto antes do `=`).
3. Formatação:
   - Preços: moeda R$, 3 casas.
   - `Paridade Etanol/Gasolina`: decimal, 2 casas.
   - `Var %`, `% Municípios…` e `% Outliers`: percentual, 1 casa.
4. Agrupe as medidas em **pastas de exibição** (Base, Tempo, Etanol x Gasolina, Detalhe, Qualidade), como no arquivo.
5. Exclua a coluna vazia da `_Medidas`. A tabela vira uma tabela de medidas, com ícone de calculadora.

## 4. Tema

**Exibir → Temas → Procurar temas** → `tema_combustiveis.json`.
Regra visual: **azul só onde está o achado, o resto em cinza**. Títulos afirmam o achado, em vez de descrever o gráfico.

## 5. Páginas

Use a mesma segmentação de **Ano** (`dData[ano]`, botões em linha) no topo de todas as páginas, sincronizada
(*Exibir → Sincronizar segmentações*). Ordem de leitura em "Z": KPIs → tendência → detalhe.

### Página 1: "Visão geral" (o gancho)

| Posição | Visual | Campos | Título |
|---|---|---|---|
| Topo, 4 cartões | Cartão | `Preço Gasolina` · `Preço Etanol` · `Paridade Etanol/Gasolina` · `Qtd Postos` | (rótulo da medida) |
| Meio, largura total | Gráfico de linhas | Eixo X: `dData[ano_mes]` · Y: `Preço Médio` · Legenda: `dProduto[produto]` (filtro do visual: GASOLINA, ETANOL, DIESEL S10) | "Gasolina subiu mais que o etanol entre 2023 e 2025" |
| Rodapé | Caixa de texto | "Fonte: ANP, Série Histórica de Preços de Combustíveis. 2,6 mi de coletas em 13,5 mil postos." | — |

### Página 2: "O achado" (página principal da história)

| Posição | Visual | Campos | Título |
|---|---|---|---|
| Topo | Cartão (texto) | `Título Achado` | (o próprio cartão é a manchete) |
| Esquerda | Barras **horizontais** | Eixo Y: `dLocalidade[uf_sigla]` · X: `Paridade Etanol/Gasolina` · ordenar **crescente** · Cores: *fx → Valor do campo →* `Cor Paridade` · Analytics: **linha constante 0,70** com rótulo "limite de 70%" | (manchete acima) |
| Direita, alto | Gráfico de linhas | X: `dData[ano_mes]` · Y: `Paridade Etanol/Gasolina` · linha constante 0,70 | "Paridade nacional: etanol compensou de ago/2023 a dez/2024 (jul–ago/2024 no limite)" |
| Direita, baixo | Cartão | `% Municípios onde Etanol Compensa` | "dos municípios pesquisados, o etanol compensou em" |

> **Interação:** clicar numa UF filtra a linha da direita. Assim fica visível que o MS fica abaixo de 70% quase o tempo todo.

### Página 3: "Na sua cidade" (detalhe e ação)

| Posição | Visual | Campos |
|---|---|---|
| Esquerda | Segmentação | Hierarquia Região → UF → Município |
| Centro | Tabela | `dLocalidade[municipio_uf]`, `Preço Etanol`, `Preço Gasolina`, `Paridade Etanol/Gasolina`, `Melhor Escolha` (formatação condicional: fundo azul claro quando "Etanol") |
| Direita | Barras agrupadas | Eixo: `dLocalidade[regiao_nome]` · Valores: `Preço Médio` · Legenda: `dBandeira[tipo_bandeira]` · filtro: produto = GASOLINA · título "Bandeira branca é ~R$ 0,18/l mais barata" |

### Página 4: "Qualidade dos dados" (técnica)

| Visual | Campos |
|---|---|
| Colunas | X: `dData[ano_mes]` · Y: `Qtd Coletas (todas)`: mostra o volume estável por mês |
| Cartões | `Qtd Coletas (todas)` · `Qtd Outliers` · `% Outliers` |
| Tabela | `dProduto[produto]`, `Qtd Coletas`, `Preço Mediano`, `Dispersão de Preço (CV)` |
| Texto | "Pipeline: CSV ANP → Pentaho (staging, limpeza, modelo estrela) → views mart → Power BI. Outliers marcados por 3×IQR, não apagados." |

## 6. Conferência obrigatória

Com a segmentação **Ano = 2025**, os valores devem bater com [`docs/kpis_referencia.csv`](../docs/kpis_referencia.csv) (calculados no notebook):

| Medida | Esperado (2025) |
|---|---|
| Preço Gasolina | R$ 6,230 |
| Preço Etanol | R$ 4,458 |
| Paridade Etanol/Gasolina | 0,72 (0,7155) |
| UFs onde Etanol Compensa | 4 (MS, MT, SP, PR) |
| % Municípios onde Etanol Compensa | 33,9% |
| Qtd Postos | 8.699 |
| Qtd Coletas | 799.859 |

Se algo não bater, as causas mais comuns são:
1. Relação em direção dupla.
2. `dData` não marcada como tabela de datas.
3. Medida sem o filtro `fl_outlier = 0`.

## 7. Salvar

Salve como `powerbi/dashboard_combustiveis.pbix`. Antes do commit, confira o tamanho, porque o GitHub recusa arquivos acima de 100 MB.
Se passar disso, remova `dRevenda[cnpj]` e as colunas não usadas, ou use Git LFS (`git lfs track "*.pbix"`).
