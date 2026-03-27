import pandas as pd
import dash
from dash import dcc, html, Input, Output, dash_table
import plotly.express as px

app=dash.Dash(__name__)
server=app.server #Modificacion
# ======================================================
# CARGA INICIAL
# ======================================================
FILE_PATH = "LEAD TIME LAVANDERIA ANALISIS.xlsx"

# def load_data(path):
#     try:
#         df = pd.read_excel(path)
#         # Normalizar nombres de columnas
#         df.columns = df.columns.str.strip().str.upper()
#         # Fechas
#         df["FECHA INGRESO"] = pd.to_datetime(df.get("FECHA INGRESO"), errors="coerce")
#         df["FECHA DE SALIDA"] = pd.to_datetime(df.get("FECHA DE SALIDA"), errors="coerce")
#         # Lead time seguro
#         if "LEAD TIME" not in df.columns:
#             df["LEAD TIME"] = 1
#         return df
#     except Exception as e:
#         print("Error cargando archivo:", e)
#         return pd.DataFrame()

# df_global = load_data(FILE_PATH)

def load_data(path):
    try:
        df = pd.read_excel(path)
    except Exception as e:
        print("Error cargando archivo:", e)
        return pd.DataFrame()

    df.columns = df.columns.str.strip().str.upper()

    df["FECHA INGRESO"] = pd.to_datetime(df.get("FECHA INGRESO"), errors="coerce")
    df["FECHA DE SALIDA"] = pd.to_datetime(df.get("FECHA DE SALIDA"), errors="coerce")

    if "LEAD TIME" not in df.columns:
        df["LEAD TIME"] = 1

    return df

# ======================================================
# APP
# ======================================================
app = dash.Dash(__name__)

app.layout = html.Div([

    dcc.Store(id="store-data", data=df_global.to_dict("records")),

    # ==============================
    # SIDEBAR
    # ==============================
    html.Div([
        html.H3("Filtros"),

        dcc.Dropdown(id="cliente", multi=True),
        dcc.Dropdown(id="clasificacion", multi=True,
                     options=[
                         {"label": "NORMAL", "value": "NORMAL"},
                         {"label": "ALTO", "value": "ALTO"},
                         {"label": "CRITICO", "value": "CRITICO"},
                     ]),

        dcc.DatePickerRange(id="fecha"),

        dcc.Upload(id="upload-data",
                   children=html.Button("Subir Excel")),

        html.Button("Limpiar datos", id="clear-data")

    ], style={"width": "20%", "display": "inline-block", "verticalAlign": "top"}),

    # ==============================
    # MAIN
    # ==============================
    html.Div([
        html.H2("🧺 Flujo Animado - Lavandería (Entrada → WIP → Salida)"),
        dcc.Graph(id="flujo"),

        html.H2("DISTRIBUCIÓN DE LEAD TIME POR CLIENTE"),
        dcc.Graph(id="boxplot"),

        html.H2("GANTT DE INGRESO Y SALIDA POR COCHE"),
        dcc.Graph(id="gantt"),

        html.H2("DETALLE DE DATOS"),
        dash_table.DataTable(id="tabla", page_size=10)
    ], style={"width": "75%", "display": "inline-block", "marginLeft": "20px"})

])

# ======================================================
# CALLBACK PRINCIPAL
# ======================================================
@app.callback(
    Output("cliente", "options"),
    Output("cliente", "value"),
    Output("flujo", "figure"),
    Output("boxplot", "figure"),
    Output("gantt", "figure"),
    Output("tabla", "data"),
    Input("store-data", "data"),
    Input("cliente", "value"),
    Input("clasificacion", "value"),
    Input("fecha", "start_date"),
    Input("fecha", "end_date"),
)
def update(data, clientes, clasif, start, end):
    df = pd.DataFrame(data)
    if df.empty:
        return [], [], {}, {}, {}, []

    # ==============================
    # MULTISELECT CLIENTES
    # ==============================
    clientes = clientes if isinstance(clientes, list) else []

    # ==============================
    # FILTROS
    # ==============================
    if clientes:
        df = df[df["CLIENTE"].isin(clientes)]

    if clasif:
        df = df[df["CLASIFICACION L.TIME"].isin(clasif)]

    if start:
        start = pd.to_datetime(start)
        df = df[df["FECHA INGRESO"] >= start]

    if end:
        end = pd.to_datetime(end)
        df = df[df["FECHA INGRESO"] <= end]

    opciones = [{"label": str(c), "value": str(c)} for c in df["CLIENTE"].dropna().unique()]

    # ==============================
    # LIMPIEZA DE FECHAS PARA FLUJO
    # ==============================
    df["FECHA INGRESO"] = pd.to_datetime(df["FECHA INGRESO"], errors="coerce")
    df["FECHA DE SALIDA"] = pd.to_datetime(df["FECHA DE SALIDA"], errors="coerce")
    df_flujo = df.dropna(subset=["FECHA INGRESO", "FECHA DE SALIDA"])

    # ======================================================
    # 🔥 FLUJO ANIMADO (Entrada → WIP → Salida)
    # ======================================================
    if df_flujo.empty:
        fig_flujo = {}
    else:
        frames = []
        fechas = pd.date_range(df_flujo["FECHA INGRESO"].min(), df_flujo["FECHA DE SALIDA"].max(), freq="D")

        for fecha in fechas:
            temp = df_flujo.copy()
            temp["FRAME"] = fecha
            temp["X"] = 0
            temp.loc[temp["FECHA INGRESO"] <= fecha, "X"] = 1
            temp.loc[temp["FECHA DE SALIDA"] <= fecha, "X"] = 2

            temp["ESTADO"] = temp["X"].map({0: "Entrada", 1: "WIP", 2: "Salida"})
            temp["Y"] = range(len(temp))

            frames.append(temp)

        sim_df = pd.concat(frames)
        sim_df["FRAME_STR"] = sim_df["FRAME"].astype(str)

        fig_flujo = px.scatter(
            sim_df,
            x="X",
            y="Y",
            animation_frame="FRAME_STR",
            color="CLASIFICACION L.TIME",
            size="LEAD TIME",
            hover_data=["COCHE", "CLIENTE"],
            labels={"X": "Estado", "Y": "Ítem"}
        )

        fig_flujo.update_layout(
            xaxis=dict(
                tickvals=[0,1,2],
                ticktext=["Entrada", "WIP", "Salida"]
            ),
            yaxis=dict(showticklabels=False),
            title="FLUJO DE PRENDAS (Entrada → WIP → Salida)"
        )

    # ======================================================
    # BOX PLOT
    # ======================================================
    fig_box = px.box(df, x="CLIENTE", y="LEAD TIME", title="DISTRIBUCIÓN DE LEAD TIME POR CLIENTE")

    # ======================================================
    # GANTT
    # ======================================================
    fig_gantt = px.timeline(
        df,
        x_start="FECHA INGRESO",
        x_end="FECHA DE SALIDA",
        y="COCHE",
        title="GANTT DE INGRESO Y SALIDA POR COCHE"
    )
    fig_gantt.update_yaxes(autorange="reversed")

    # ======================================================
    # TABLA
    # ======================================================
    data_tabla = df.to_dict("records")

    return opciones, clientes, fig_flujo, fig_box, fig_gantt, data_tabla

# ======================================================
# RUN
# ======================================================
if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=10000)
