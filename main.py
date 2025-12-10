import os
import json
import zipfile
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from groq import Groq
from tavily import TavilyClient
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

# Carrega .env local (no Render, ele vai ignorar isso e pegar das vars do sistema)
load_dotenv()

# --- CONFIGURAÇÃO SEGURA DOS AGENTES ---
try:
    client_groq = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    client_tavily = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))
except Exception as e:
    print(f"⚠️ Aviso API: {e}")

# --- CARREGAMENTO DO CÉREBRO (CHROMA) ---
# Nota: Na nuvem, o Chroma local resetará a cada deploy a menos que use disco persistente.
# Para a apresentação, isso não é problema, pois ele roda na memória ou recria se vazio.
rag_ciencia = rag_taco = rag_fndds = rag_agua = rag_leis = None

try:
    chroma = chromadb.PersistentClient(path="./banco_vetorial")
    emb_fn = embedding_functions.DefaultEmbeddingFunction()
    
    try: rag_ciencia = chroma.get_collection("artigos_cientificos", embedding_function=emb_fn)
    except: pass
    
    try: rag_taco = chroma.get_collection("taco_nutricao", embedding_function=emb_fn) 
    except: 
        try: rag_taco = chroma.get_collection("nutri_taco", embedding_function=emb_fn)
        except: pass

    try: rag_fndds = chroma.get_collection("fndds_nutricao", embedding_function=emb_fn)
    except: 
        try: rag_fndds = chroma.get_collection("nutri_fndds", embedding_function=emb_fn)
        except: pass
        
    try: rag_agua = chroma.get_collection("dados_agua", embedding_function=emb_fn)
    except: pass
    
    try: rag_leis = chroma.get_collection("legislacao_anvisa", embedding_function=emb_fn)
    except: pass
    
    print("🧠 Memória Vetorial Carregada!")
except Exception as e:
    print(f"⚠️ Aviso: O Banco Vetorial falhou ou iniciou vazio ({e}).")

app = FastAPI()

# Configuração CORS (Permissiva para garantir que funcione na demo)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- SERVIR ARQUIVOS ESTÁTICOS (FRONTEND INTEGRADO) ---
# Isso permite que o Backend entregue o site, facilitando o deploy em 1 serviço só.
# Certifique-se de ter movido index.html, css/ e js/ para a pasta 'static'
try:
    app.mount("/css", StaticFiles(directory="static/css"), name="css")
    app.mount("/js", StaticFiles(directory="static/js"), name="js")
    # Se tiver assets, descomente abaixo:
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
except Exception as e:
    print(f"⚠️ Aviso Estático: Pastas css/js não encontradas em 'static/'. {e}")

@app.get("/")
async def read_root():
    # Retorna o index.html quando acessa a raiz
    return FileResponse('static/index.html')

# --- MODELOS ---
class IngredienteExtra(BaseModel):
    nome: str
    operador: str = "AND"
    quantidade: Optional[str] = None

class PedidoEngenharia(BaseModel):
    residuo_principal: str
    nivel_producao: str
    produto_alvo: Optional[str] = None
    quantidade_semanal: Optional[str] = None
    ingredientes_extras: List[IngredienteExtra] = []
    modo_avancado: bool = False

# --- FUNÇÕES ---

def consultar_rag(collection, query, n=1):
    if not collection or collection.count() == 0: return ""
    try:
        res = collection.query(query_texts=[query], n_results=n)
        if res['documents'][0]:
            return "\n---\n".join(res['documents'][0])
        return ""
    except: return ""

def traduzir_termo(termo):
    try:
        chat = client_groq.chat.completions.create(
            messages=[{"role": "user", "content": f"Translate '{termo}' to English food term. Output ONLY the English term."}],
            model="llama-3.1-8b-instant"
        )
        return chat.choices[0].message.content.strip()
    except: return termo

def pesquisar_economia_segura(termo, nivel):
    print(f"💰 Buscando economia: {termo}...")
    try:
        query = f"preço atacado {termo} brasil site:cepea.esalq.usp.br OR site:noticiasagricolas.com.br"
        res = client_tavily.search(query=query, search_depth="basic", max_results=1)
        return "\n".join([r["content"] for r in res["results"]])
    except: return "Dados offline."

def limpar_json(texto):
    try:
        inicio = texto.find('[')
        fim = texto.rfind(']') + 1
        if inicio != -1 and fim != -1:
            return json.loads(texto[inicio:fim])
        inicio = texto.find('{')
        fim = texto.rfind('}') + 1
        if inicio != -1 and fim != -1:
            obj = json.loads(texto[inicio:fim])
            if "resultados" in obj: return obj["resultados"]
            return [obj]
    except: pass
    return None

def gerar_com_fallback(messages):
    modelos = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
    for modelo in modelos:
        try:
            print(f"🤖 Gerando com: {modelo}...")
            return client_groq.chat.completions.create(
                messages=messages, model=modelo, temperature=0.3, response_format={"type": "json_object"}
            )
        except Exception as e:
            print(f"⚠️ Falha no modelo {modelo}: {e}")
            continue
    raise HTTPException(status_code=429, detail="API Ocupada. Tente em 1 min.")

# --- ROTA PRINCIPAL ---

@app.post("/gerar-solucao")
async def gerar_solucao(pedido: PedidoEngenharia):
    print(f"🚀 Processando: {pedido.residuo_principal}")

    # 1. RAG OTIMIZADO (Query Expansion)
    termo_en = traduzir_termo(pedido.residuo_principal)
    
    dados_ciencia = consultar_rag(rag_ciencia, f"technological process parameters {termo_en} valorization temperature time conditions", n=2)
    dados_lei = consultar_rag(rag_leis, f"regulamento técnico identidade qualidade {pedido.residuo_principal} requisitos físico-químicos", n=2)
    dados_taco = consultar_rag(rag_taco, pedido.residuo_principal, n=1)
    dados_fndds = consultar_rag(rag_fndds, termo_en, n=1)
    dados_agua = consultar_rag(rag_agua, f"pegada hídrica {pedido.residuo_principal}", n=1)
    dados_mercado = pesquisar_economia_segura(pedido.residuo_principal, pedido.nivel_producao)

    str_ingredientes = ""
    if pedido.ingredientes_extras:
        lista = [f"{'OU' if i.operador=='OR' else 'E'} {i.nome} ({i.quantidade or ''})" for i in pedido.ingredientes_extras]
        str_ingredientes = f"INGREDIENTES EXTRAS: {' '.join(lista)}"

    objetivo = pedido.produto_alvo if pedido.produto_alvo else "Sugira inovações viáveis"
    
    # 3. PROMPT RIGOROSO (Engenharia Sênior + Pitch Deck)
    # ALTERAÇÃO: Forçado a gerar 4 sugestões para a lógica Freemium funcionar
    prompt_sistema = f"""
    ATUE COMO: Engenheiro de Alimentos Sênior e Especialista Regulatório.
    
    === DOSSIÊ TÉCNICO (Contexto Recuperado) ===
    [NUTRIÇÃO - TACO/FNDDS]: {dados_taco} / {dados_fndds}
    [CIÊNCIA - PROCESSOS]: {dados_ciencia}
    [LEGISLAÇÃO - ANVISA]: {dados_lei}
    [MERCADO]: {dados_mercado}
    ============================================

    PEDIDO:
    Matéria-prima: {pedido.residuo_principal}. Escala: {pedido.nivel_producao}.
    {str_ingredientes}
    Objetivo: {objetivo}. 
    
    *** INSTRUÇÃO DE DEMO ***
    Gere OBRIGATORIAMENTE 4 sugestões.
    
    --- REGRAS DE OURO ---
    1. NUTRIÇÃO OBRIGATÓRIA: Use os dados do bloco [NUTRIÇÃO]. Se não houver correspondência exata, ESTIME com base na matéria-prima similar. NUNCA deixe valores vazios ou zerados.
    2. LEGISLAÇÃO: Cite a RDC/IN específica encontrada no bloco [LEGISLAÇÃO] que valida a categoria do produto.
    3. FLUXOGRAMA: Detalhe os parâmetros (Temp/Tempo) citados no bloco [CIÊNCIA].
    4. ESCALA: Se for "Serviços de Alimentação" ou "Artesanal", foque em equipamentos de cozinha industrial (fornos, liquidificadores) e não torres de secagem.

    --- FORMATO JSON OBRIGATÓRIO ---
    {{
        "resultados": [
            {{
                "nivel": "{pedido.nivel_producao}",
                "nome": "Nome Técnico 1",
                "pitch": "Resumo comercial...",
                "categoria_visual": "ALIMENTO_SOLIDO",
                "visual_prompt_en": "Description...",
                "validade_estimada": "XX dias",
                "lista_ingredientes": "...",
                "fluxograma": ["1. Recepção", "2. Processo X (XX°C/XXmin)", "3. ..."],
                "seguranca": "Conforme RDC nº... (Baseado no contexto)",
                "nutricao": {{ 
                    "porcao": "100g",
                    "valor_energetico": "XX kcal", 
                    "carboidratos": "XX g", 
                    "acucares_totais": "XX g",
                    "acucares_adicionados": "XX g",
                    "proteinas": "XX g", 
                    "gorduras_totais": "XX g", 
                    "gorduras_saturadas": "XX g",
                    "fibra_alimentar": "XX g",
                    "sodio": "XX mg", 
                    "alertas_fop": ["ALTO EM AÇÚCAR ADICIONADO?"] 
                }},
                "sustentabilidade": {{ "agua_economizada_litros_100kg": 0, "agua_gasta_processo_litros_100kg": 0 }},
                "economia": {{ "custo_producao_estimado": "R$...", "preco_venda_estimado": "R$...", "margem_lucro": "%", "investimento_inicial": "R$...", "roi_estimado": "meses" }},
                "regiao": "Brasil"
            }},
            {{ "nome": "Solução 2...", ... }},
            {{ "nome": "Solução 3...", ... }},
            {{ "nome": "Solução 4...", ... }}
        ]
    }}
    """

    completion = gerar_com_fallback([{"role": "system", "content": prompt_sistema}])
    
    raw_content = completion.choices[0].message.content
    try: content = json.loads(raw_content)
    except: 
        content = limpar_json(raw_content)
        if not content: raise ValueError("Erro JSON IA")

    lista_final = []
    if isinstance(content, dict):
        if "resultados" in content: lista_final = content["resultados"]
        elif "solucoes" in content: lista_final = content["solucoes"]
        else: lista_final = [content]
    elif isinstance(content, list): lista_final = content
    
    if len(lista_final) > 0 and isinstance(lista_final[0], list): lista_final = lista_final[0]

    return lista_final

if __name__ == "__main__":
    import uvicorn
    # Host 0.0.0.0 é obrigatório para rodar em containers (Render)
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))