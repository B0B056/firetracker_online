import streamlit as st
import pandas as pd
import json
from pathlib import Path
import plotly.express as px
from datetime import date, datetime


# Caminhos dos ficheiros
REFORCOS_CSV = Path("data/reforcos.csv")
SIMULACOES_CSV = Path("data/simulacoes.csv")
CORES_ATIVOS_CSV = Path("data/cores_ativos.csv")

# Configuração da página
st.set_page_config(page_title="🔥 FIRE Tracker", layout="wide")

# Caminhos para as pastas 
DATA_DIR = Path(__file__).parent / "data"
utilizador_path = DATA_DIR / "utilizador.json"

def calcular_simulacao_fire(valor_atual, reforco_mensal, taxa_juros_anual, objetivo, idade_atual, idade_reforma):
    meses_ate_reforma = max(0, (idade_reforma - idade_atual) * 12)
    valores_fire = []
    valores_coast = []

    valor_fire = valor_atual
    valor_coast = valor_atual
    taxa_mensal = (1 + taxa_juros_anual) ** (1/12) - 1

    mes = None
    for mes in range(meses_ate_reforma):
        # FIRE: acumulando com reforços mensais
        valor_fire = valor_fire * (1 + taxa_mensal) + reforco_mensal
        valores_fire.append(valor_fire)

        # Coast FIRE: valor atual cresce sem reforços
        valor_coast = valor_coast * (1 + taxa_mensal)
        valores_coast.append(valor_coast)

        if valor_fire >= objetivo:
            break

    if mes is not None:
        anos_ate_fire = (mes + 1) / 12  # +1 because range starts at 0
    else:
        anos_ate_fire = 0

    return anos_ate_fire, valores_fire, valores_coast

# Funções para carregar ficheiros
def carregar_csv(nome_ficheiro):
    caminho = DATA_DIR / nome_ficheiro
    if caminho.exists():
        return pd.read_csv(caminho)
    else:
        st.warning(f"⚠️ Ficheiro {nome_ficheiro} não encontrado.")
        return pd.DataFrame()
def carregar_json(nome_ficheiro):
    caminho = DATA_DIR / nome_ficheiro
    if caminho.exists():
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        st.warning(f"⚠️ Ficheiro {nome_ficheiro} não encontrado.")
        return {}
def carregar_cores_csv():
    """Lê o ficheiro cores_ativos.csv e devolve um dicionário {Ativo: cor}"""
    if CORES_ATIVOS_CSV.exists():
        df = pd.read_csv(CORES_ATIVOS_CSV)
        return dict(zip(df["Ativo"], df["Cor"]))
    return {}
def _to_number(series: pd.Series) -> pd.Series:

    """Tenta converter strings numéricas com formatos diversos para float."""
    s = series.astype(str).fillna("").str.strip()
    # remover símbolos (€, spaces, letras)
    # primeiro: eliminar pontos que provavelmente são separadores de milhares (ex: 1.234,56 -> 1234,56)
    s = s.str.replace(r'\.(?=\d{3}(?:[^\d]|$))', '', regex=True)
    # substituir vírgula decimal por ponto
    s = s.str.replace(',', '.', regex=False)
    # remover tudo o que não seja dígito, ponto ou menos
    s = s.str.replace(r'[^\d\.-]', '', regex=True)
    return pd.to_numeric(s, errors='coerce')
# Carregar dados
simulacoes = carregar_csv("simulacoes.csv")
cores_ativos = carregar_cores_csv()
utilizador = carregar_json("utilizador.json")
def carregar_dados_utilizador():
    """Carrega o ficheiro de utilizador, cria se não existir."""
    if not utilizador_path.exists():
        dados_iniciais = {"data_nascimento": None}
        with open(utilizador_path, "w", encoding="utf-8") as f:
            json.dump(dados_iniciais, f, ensure_ascii=False, indent=4)
        return dados_iniciais
    
    try:
        with open(utilizador_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Em caso de ficheiro corrompido, recriar
        dados_iniciais = {"data_nascimento": None}
        with open(utilizador_path, "w", encoding="utf-8") as f:
            json.dump(dados_iniciais, f, ensure_ascii=False, indent=4)
        return dados_iniciais
def guardar_dados_utilizador(dados):
    """Grava o ficheiro de utilizador."""
    with open(utilizador_path, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)
def calcular_idade(yyyy_mm_dd_str):
    if not yyyy_mm_dd_str:
        return None
    nasc = datetime.strptime(yyyy_mm_dd_str, "%Y-%m-%d").date()
    hoje = date.today()
    return hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
# ---- Funções das páginas ----
def pagina_dashboard():
    st.title("📊 Dashboard")

    # --------------------
    # 1️⃣ Resumo FIRE
    # --------------------
    if SIMULACOES_CSV.exists():
        df_sim = pd.read_csv(SIMULACOES_CSV)
        if not df_sim.empty:
            ultima = df_sim.iloc[-1]
            col1, col2, col3 = st.columns(3)
            col1.metric("🎯 FIRE", f"{ultima['FIRE (€)']:,.2f}€")
            col2.metric("🏖️ Coast FIRE", f"{ultima['Coast FIRE (€)']:,.2f}€")
            col3.metric("📅 Idade Reforma", f"{int(ultima['Idade Reforma'])} anos")
        else:
            st.info("Ainda não existem simulações guardadas.")
    else:
        st.warning("⚠️ Ficheiro de simulações não encontrado.")

    st.markdown("---")

    if not REFORCOS_CSV.exists():
        st.warning("⚠️ Ficheiro de reforços não encontrado.")
        return

    df = pd.read_csv(REFORCOS_CSV)

    if df.empty:
        st.info("Ainda não existem reforços registados para gerar gráficos.")
        return

    # Garantir colunas necessárias
    colunas_minimas = ["Data", "Ativo", "Quantidade", "Valor Investido (€)", "Valor do Portefólio (€)"]
    for col in colunas_minimas:
        if col not in df.columns:
            df[col] = 0

    # Tratar datas
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df = df.sort_values("Data")

    # Preencher valores nulos e converter para numérico
    for col in ["Quantidade", "Valor Investido (€)", "Valor do Portefólio (€)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Calcular total acumulado dos reforços
    df["Total_Acumulado"] = df["Valor Investido (€)"].cumsum()

    # 📊 Gráfico combinado: Total Acumulado vs Valor do Portefólio
    fig_combo = px.line(
        df,
        x="Data",
        y=["Total_Acumulado", "Valor do Portefólio (€)"],
        title="📈 Total Acumulado vs Valor do Portefólio",
        labels={"value": "Valor (€)", "variable": "Série"},
        hover_data={"Data": True, "value": ":,.2f"}
    )
    st.plotly_chart(fig_combo, use_container_width=True)

    # 📦 Gráfico quantidade/mês por ativo
    if "Quantidade" in df.columns and "Ativo" in df.columns:
        df["AnoMes"] = df["Data"].dt.to_period("M").astype(str)
        resumo = df.groupby(["AnoMes", "Ativo"], as_index=False)["Quantidade"].sum()

        fig_qtd = px.bar(
            resumo,
            x="AnoMes",
            y="Quantidade",
            color="Ativo",
            title="📦 Quantidade/Mês por Ativo",
            labels={"AnoMes": "Mês", "Quantidade": "Quantidade Total"}
        )
        st.plotly_chart(fig_qtd, use_container_width=True)

def carregar_ativos_existentes():
    """Lê os ativos únicos do CSV de reforços."""
    if REFORCOS_CSV.exists():
        df = pd.read_csv(REFORCOS_CSV)
        if "Ativo" in df.columns and not df.empty:
            return sorted(df["Ativo"].dropna().unique().tolist())

def guardar_reforco(data, ativo, quantidade, valor, rentabilidade, valor_portefolio=None):
    """Guarda um novo reforço no CSV, garantindo todas as colunas necessárias."""
    novo = pd.DataFrame([{
        "Data": data.strftime("%Y-%m-%d") if hasattr(data, "strftime") else data,
        "Ativo": ativo.strip() if isinstance(ativo, str) else ativo,
        "Quantidade": quantidade if quantidade is not None else 0,
        "Valor Investido (€)": valor if valor is not None else 0,
        "Rentabilidade (%)": rentabilidade if rentabilidade is not None else 0,
        "Valor do Portefólio (€)": valor_portefolio if valor_portefolio is not None else 0
    }])

    # Garantir que o ficheiro e colunas existem
    if REFORCOS_CSV.exists():
        df = pd.read_csv(REFORCOS_CSV)
        for col in novo.columns:
            if col not in df.columns:
                df[col] = None
        df = pd.concat([df, novo], ignore_index=True)
    else:
        df = novo

    df.to_csv(REFORCOS_CSV, index=False)

def pagina_adicionar_reforco():
    st.title("➕ Adicionar Reforço")

    # Carregar lista de ativos já existentes
    ativos_existentes = []
    if REFORCOS_CSV.exists():
        _df = pd.read_csv(REFORCOS_CSV)
        if "Ativo" in _df.columns and not _df.empty:
            ativos_existentes = sorted(
                [a for a in _df["Ativo"].dropna().unique().tolist() if str(a).strip() != ""]
            )

    # Opções: criar novo ou escolher existente
    opcoes_ativos = ["➕ Criar novo ativo"] + ativos_existentes

    with st.form("form_reforco"):
        col1, col2 = st.columns(2)

        with col1:
            data = st.date_input("📅 Data", value=date.today())

            # Selectbox com estado guardado
            escolha_ativo = st.selectbox(
                "🏷️ Ativo",
                opcoes_ativos,
                index=0 if "escolha_ativo" not in st.session_state else
                opcoes_ativos.index(st.session_state["escolha_ativo"]) 
                if st.session_state["escolha_ativo"] in opcoes_ativos else 0,
                key="escolha_ativo"
            )

            # Se criar novo ativo, mostrar campo de texto
            if escolha_ativo == "➕ Criar novo ativo":
                ativo = st.text_input("Novo ativo", key="novo_ativo").strip()
            else:
                ativo = escolha_ativo.strip()

            quantidade = st.number_input("📦 Quantidade", min_value=0.0, step=0.01, format="%.2f")

        with col2:
            valor = st.number_input("💰 Valor Investido (€)", min_value=0.0, step=0.01, format="%.2f")
            rentabilidade = st.number_input("📈 Rentabilidade (%)", step=0.01, format="%.2f")
            valor_portfolio = st.number_input("💼 Valor do Portefólio (€)", min_value=0.0, step=0.01, format="%.2f")

        submitted = st.form_submit_button("💾 Guardar Reforço")

        if submitted:
            if ativo == "":
                st.error("⚠️ O nome do ativo é obrigatório.")
            else:
                guardar_reforco(data, ativo, quantidade, valor, rentabilidade, valor_portfolio)
                st.success(f"Reforço em '{ativo}' guardado com sucesso!")
                st.rerun()

    # Mostrar reforços existentes
    if REFORCOS_CSV.exists():
        st.subheader("📋 Reforços registados")
        df = pd.read_csv(REFORCOS_CSV)
        st.dataframe(df)
    else:
        st.info("Ainda não existem reforços registados.")

def pagina_editar_mes():
    st.title("✏️ Editar Mês")

    colunas_obrigatorias = [
        "Data", "Ativo", "Quantidade", "Valor Investido (€)", "Rentabilidade (%)", "Valor do Portefólio (€)"
    ]

    if REFORCOS_CSV.exists():
        df = pd.read_csv(REFORCOS_CSV)

        # Garantir colunas obrigatórias
        for col in colunas_obrigatorias:
            if col not in df.columns:
                df[col] = None

        # Adicionar coluna para selecionar linhas a apagar
        if "Apagar" not in df.columns:
            df["Apagar"] = False

        # Formatar e ordenar dados
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.strftime("%Y-%m-%d")
        for col in ["Quantidade", "Valor Investido (€)", "Rentabilidade (%)", "Valor do Portefólio (€)"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").round(2)
        df.sort_values("Data", ascending=False, inplace=True)

        # Filtro rápido por Ativo
        ativos_unicos = ["Todos"] + sorted(df["Ativo"].dropna().unique())
        filtro_ativo = st.selectbox("🔍 Filtrar por Ativo", ativos_unicos)
        if filtro_ativo != "Todos":
            df = df[df["Ativo"] == filtro_ativo]

        st.info("🖊️ Altere os valores diretamente na tabela ou marque linhas para apagar.")

        # Configuração das colunas
        column_config = {
            "Rentabilidade (%)": st.column_config.ProgressColumn(
                "Rentabilidade (%)",
                help="Percentagem de rentabilidade",
                min_value=-100,
                max_value=100,
                format="%.2f"
            ),
            "Quantidade": st.column_config.NumberColumn("Quantidade", format="%.2f"),
            "Valor Investido (€)": st.column_config.NumberColumn("Valor Investido (€)", format="%.2f"),
            "Valor do Portefólio (€)": st.column_config.NumberColumn("Valor do Portefólio (€)", format="%.2f"),
            "Apagar": st.column_config.CheckboxColumn("Apagar"),
        }

        # Editor
        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            hide_index=True,
            column_config=column_config,
            use_container_width=True
        )

        col1, col2 = st.columns(2)

        # Guardar edições
        with col1:
            if st.button("💾 Guardar Alterações"):
                df_editado = edited_df.copy()
                if "Apagar" in df_editado.columns:
                    df_editado = df_editado.drop(columns=["Apagar"])
                df_editado["Data"] = pd.to_datetime(df_editado["Data"], errors="coerce").fillna(pd.Timestamp.today())
                df_editado.sort_values("Data", ascending=False, inplace=True)
                df_editado.to_csv(REFORCOS_CSV, index=False)
                st.success("✅ Alterações guardadas com sucesso!")
                st.rerun()

        # Apagar linhas selecionadas
        with col2:
            if st.button("🗑️ Apagar Linhas Selecionadas"):
                linhas_apagar = edited_df[edited_df["Apagar"] == True]
                if not linhas_apagar.empty:
                    df_restante = edited_df[edited_df["Apagar"] != True]
                    if "Apagar" in df_restante.columns:
                        df_restante = df_restante.drop(columns=["Apagar"])
                    df_restante["Data"] = pd.to_datetime(df_restante["Data"], errors="coerce").fillna(pd.Timestamp.today())
                    df_restante.sort_values("Data", ascending=False, inplace=True)
                    df_restante.to_csv(REFORCOS_CSV, index=False)
                    st.success(f"🗑️ {len(linhas_apagar)} linha(s) apagada(s) com sucesso!")
                    st.rerun()
                else:
                    st.warning("⚠️ Nenhuma linha foi selecionada para apagar.")

    else:
        st.warning("⚠️ Ainda não existem reforços registados.")

def pagina_simulador():
    st.title("🧮 Simulador FIRE")

    dados_utilizador = carregar_dados_utilizador()

    # Se não houver data de nascimento, pedir primeiro
    
    if not dados_utilizador.get("data_nascimento"):
        st.warning("⚠️ Antes de continuar, introduza a sua data de nascimento.")
        nova_data = st.date_input("📅 Data de Nascimento", value=date(1990, 1, 1))
        if st.button("💾 Guardar Data"):
            dados_utilizador["data_nascimento"] = nova_data.strftime("%Y-%m-%d")
            guardar_dados_utilizador(dados_utilizador)
            st.success("✅ Data de nascimento guardada. Pode agora utilizar o simulador.")
            st.rerun()
        return
    else:
        # Converter string para date antes de usar novamente
        try:
            data_nasc = datetime.strptime(dados_utilizador["data_nascimento"], "%Y-%m-%d").date()
            idade_atual = calcular_idade(dados_utilizador.get("data_nascimento")) or 0
        except ValueError:
            data_nasc = date(1990, 1, 1)  # valor padrão se algo correr mal
            idade_atual = 0
        except Exception:
            data_nasc = date(1990, 1, 1)
            idade_atual = 0
    # ---- Inputs ----
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("👤 Idade Atual", min_value=0, max_value=120, value=idade_atual, key="idade_atual_input")
        valor_atual = st.number_input("💰 Valor Atual do Portefólio (€)", min_value=0.0, value=0.0, step=100.0)
        reforco_mensal = st.number_input("📆 Reforço Mensal (€)", min_value=0.0, value=500.0, step=50.0)
    with col2:
        idade_reforma = st.number_input("📅 Idade de Reforma", min_value=idade_atual, max_value=120, value=max(idade_atual+1, 65))
        taxa_juros = st.number_input("📈 Taxa de Crescimento Anual (%)", min_value=0.0, value=5.0, step=0.1) / 100.0
        objetivo = st.number_input("🎯 Objetivo FIRE (€)", min_value=0.0, value=500000.0, step=1000.0)

    guardar_no_historico = st.checkbox("💾 Guardar esta simulação no histórico?")

    st.markdown("---")

    if st.button("Calcular Simulação"):
        # Chamar a tua função já existente
        anos, valores, _ = calcular_simulacao_fire(valor_atual, reforco_mensal, taxa_juros, objetivo, idade_atual, idade_reforma)

        st.success(f"⏳ Vais atingir o FIRE em aproximadamente **{anos:.1f} anos**.")

        fig_fire = px.line(
            x=list(range(len(valores))),
            y=valores,
            title="🔥 Projeção FIRE",
            labels={"x": "Meses", "y": "Valor (€)"}
        )
        st.plotly_chart(fig_fire, use_container_width=True)

        if guardar_no_historico:
            nova_sim = pd.DataFrame([{
                "Data": datetime.now().strftime("%Y-%m-%d"),
                "Idade Atual": idade_atual,
                "Idade Reforma": idade_reforma,
                "Valor Portefólio (€)": valor_atual,
                "Reforço Mensal (€)": reforco_mensal,
                "Taxa (%)": taxa_juros * 100.0,
                "FIRE (€)": objetivo
            }])

            if SIMULACOES_CSV.exists():
                df_sim = pd.read_csv(SIMULACOES_CSV)
                hoje = datetime.now().strftime("%Y-%m-%d")
                if "Data" in df_sim.columns:
                    df_sim = df_sim[df_sim["Data"] != hoje]
                df_sim = pd.concat([df_sim, nova_sim], ignore_index=True)
            else:
                df_sim = nova_sim

            df_sim.to_csv(SIMULACOES_CSV, index=False)
            st.success("✅ Simulação guardada no histórico.")


def pagina_cores_tema():
    st.title("🎨 Cores e Tema")
    st.dataframe(cores_ativos)

# ---- Barra lateral ----
st.sidebar.title("🔥 FIRE Tracker")
menu = st.sidebar.radio(
    "Navegação",
    ["📊 Dashboard", "➕ Adicionar Reforço", "✏️ Editar Mês", "🧮 Simulador FIRE", "🎨 Cores e Tema"]
)

# ---- Mostrar página selecionada ----
if menu == "📊 Dashboard":
    pagina_dashboard()
elif menu == "➕ Adicionar Reforço":
    pagina_adicionar_reforco()
elif menu == "✏️ Editar Mês":
    pagina_editar_mes()
elif menu == "🧮 Simulador FIRE":
    pagina_simulador()
elif menu == "🎨 Cores e Tema":
    pagina_cores_tema()
