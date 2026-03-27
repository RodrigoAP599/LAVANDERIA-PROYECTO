import pandas as pd
import dash
from dash import dcc, html, Input, Output, State, dash_table
import plotly.express as px
import base64
import io

# ======================================================
# FUNCION DE CARGA
# ======================================================
def load_data(contents):
    try:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)

        df = pd.read_excel(io.BytesIO(decoded))

        df.columns = df.columns.str.strip().str.upper()

        df["FECHA INGRESO"] = pd.to_datetime(df.get("FECHA INGRESO"), errors="coerce")
        df["FECHA DE SALIDA"] = pd.to_datetime(df.get("FECHA DE SALIDA"), errors="coerce")

        if "LEAD TIME" not in df.columns:
            df["LEAD TIME"] = 1

        return df

    except Exception as e:
        print("Error cargando archivo:", e)
        return pd.DataFrame()
    
df.columns = df.columns.str.strip().str.upper()

# MAPEO FLEXIBLE
rename_map = {
    "CLIENTE ": "CLIENTE",
    "CLIENTE": "CLIENTE",
    "CLASIFICACIÓN L.TIME": "CLASIFICACION L.TIME",
    "CLASIFICACION": "CLASIFICACION L.TIME",
    "FECHA INGRESO": "FECHA INGRESO",
    "FECHA DE INGRESO": "FECHA INGRESO",
    "FECHA SALIDA": "FECHA DE SALIDA",
    "COCHE ": "COCHE",
}

df.rename(columns=rename_map, inplace=True)

# ======================================================
# APP
# ======================================================
app = dash.Dash(__name__)
server = app.server  # 👈 IMPORTANTE PARA RENDER

app.layout = html.Div([

    dcc.Store(id="store-data", data=[]),

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

        dcc.Upload(
            id="upload-data",
            children=html.Button("Subir Excel"),
            multiple=False
        ),

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
# CALLBACK: CARGA DE ARCHIVO
# ======================================================
@app.callback(
    Output("store-data", "data"),
    Input("upload-data", "contents"),
    Input("clear-data", "n_clicks"),
    prevent_initial_call=True
)
def handle_upload(contents, clear_clicks):
    ctx = dash.callback_context

    if not ctx.triggered:
        return []

    trigger = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger == "clear-data":
        return []

    if contents:
        df = load_data(contents)
        return df.to_dict("records")

    return []


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

    clientes = clientes if isinstance(clientes, list) else []

    if "CLIENTE" in df.columns and clientes:
        df = df[df["CLIENTE"].isin(clientes)]

    if "CLASIFICACION L.TIME" in df.columns and clasif:
        df = df[df["CLASIFICACION L.TIME"].isin(clasif)]

    if start and "FECHA INGRESO" in df.columns:
        df = df[df["FECHA INGRESO"] >= pd.to_datetime(start)]

    if end and "FECHA INGRESO" in df.columns:
        df = df[df["FECHA INGRESO"] <= pd.to_datetime(end)]

    opciones = []
    if "CLIENTE" in df.columns:
        opciones = [{"label": str(c), "value": str(c)} for c in df["CLIENTE"].dropna().unique()]

    # ==============================
    # FLUJO
    # ==============================
    df_flujo = df.dropna(subset=["FECHA INGRESO", "FECHA DE SALIDA"]) if "FECHA INGRESO" in df.columns and "FECHA DE SALIDA" in df.columns else pd.DataFrame()

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
            color="CLASIFICACION L.TIME" if "CLASIFICACION L.TIME" in sim_df.columns else None,
            size="LEAD TIME" if "LEAD TIME" in sim_df.columns else None,
            hover_data=["COCHE", "CLIENTE"] if "COCHE" in sim_df.columns else None,
        )

    # ==============================
    # BOX
    # ==============================
    fig_box = px.box(df, x="CLIENTE", y="LEAD TIME") if "CLIENTE" in df.columns else {}

    # ==============================
    # GANTT
    # ==============================
    if "FECHA INGRESO" in df.columns and "FECHA DE SALIDA" in df.columns and "COCHE" in df.columns:
        fig_gantt = px.timeline(df, x_start="FECHA INGRESO", x_end="FECHA DE SALIDA", y="COCHE")
        fig_gantt.update_yaxes(autorange="reversed")
    else:
        fig_gantt = {}

    return opciones, clientes, fig_flujo, fig_box, fig_gantt, df.to_dict("records")


# ======================================================
# RUN LOCAL
# ======================================================
if __name__ == "__main__":
    app.run_server(debug=True)
