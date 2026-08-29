import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from tavily import TavilyClient
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

# Novas bibliotecas
from openai import OpenAI
from google import genai
from google.genai import types

load_dotenv()

# --- CONFIGURAÇÃO DOS AGENTES ---
try:
    client_principal = OpenAI(
        api_key=os.environ.get("OPENROUTER_API_KEY"), 
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://ecofood-sgcz.onrender.com", # Obrigatório para modelos grátis
            "X-Title": "EcoFood Pro" # Identificação
        }
    )
    client_tavily = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))
    
    gemini_key = os.environ.get("GEMINI_API_KEY")
    client_gemini = genai.Client(api_key=gemini_key) if gemini_key else None
except Exception as e:
    print(f"Aviso API: {e}")

# --- CARREGAMENTO DO CÉREBRO (CHROMA) ---
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
    
    print("Memoria Vetorial Carregada!")
except Exception as e:
    print(f"Aviso: O Banco Vetorial falhou ou iniciou vazio ({e}).")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- SERVIR ARQUIVOS ESTÁTICOS ---
try:
    app.mount("/css", StaticFiles(directory="static/css"), name="css")
    app.mount("/js", StaticFiles(directory="static/js"), name="js")
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
except Exception as e:
    print(f"Aviso Estatico: Pastas css/js nao encontradas. {e}")

@app.get("/")
async def read_root():
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
    provedor: str = "deepseek"

# --- FUNÇÕES AUXILIARES ---
def consultar_rag(collection, query, n=1):
    if not collection or collection.count() == 0: return ""
    try:
        res = collection.query(query_texts=[query], n_results=n)
        if res['documents'][0]: return "\n---\n".join(res['documents'][0])
        return ""
    except: return ""

def traduzir_termo(termo):
    try:
        response = client_deepseek.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": f"Translate '{termo}' to English food term. Output ONLY the English term."}],
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    except: return termo

def pesquisar_economia_segura(termo, nivel):
    print(f"Buscando economia: {termo}...")
    try:
        query = f"preço atacado {termo} brasil site:cepea.esalq.usp.br OR site:noticiasagricolas.com.br"
        res = client_tavily.search(query=query, search_depth="basic", max_results=1)
        return "\n".join([r["content"] for r in res["results"]])
    except: return "Dados offline."

def limpar_json(texto):
    try:
        inicio = texto.find('[')
        fim = texto.rfind(']') + 1
        if inicio != -1 and fim != -1: return json.loads(texto[inicio:fim])
        
        inicio = texto.find('{')
        fim = texto.rfind('}') + 1
        if inicio != -1 and fim != -1:
            obj = json.loads(texto[inicio:fim])
            if "resultados" in obj: return obj["resultados"]
            return [obj]
    except: pass
    return None

# --- FUNÇÕES DE CHAMADA ISOLADAS E FALLBACK ---
def chamar_gemini(messages):
    try:
        print("Gerando com Google Gemini (2.5-flash)...")
        prompt_texto = messages[0]["content"] 
        response = client_gemini.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt_texto,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
        )
        return response.text
    except Exception as e:
        print(f"Falha critica no Gemini: {e}")
        raise HTTPException(status_code=500, detail="Todas as APIs indisponiveis.")

def chamar_principal(messages):
    try:
        print("Gerando com OpenRouter (Modelo Gratuito)...")
        response = client_principal.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct:free", # Versão 3.1
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Falha no OpenRouter: {e}. Acionando fallback para Gemini...")
        return chamar_gemini(messages)

# --- ROTA PRINCIPAL ---
@app.post("/gerar-solucao")
async def gerar_solucao(pedido: PedidoEngenharia):
    print(f"Processando ({pedido.provedor}): {pedido.residuo_principal}")

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
    
    prompt_sistema = f"""
    ATUE COMO: Cientista de Alimentos Sênior e Especialista Regulatório.
    
    === DOSSIÊ TÉCNICO ===
    [NUTRIÇÃO]: {dados_taco} / {dados_fndds}
    [CIÊNCIA]: {dados_ciencia}
    [LEGISLAÇÃO]: {dados_lei}
    [MERCADO]: {dados_mercado}
    ======================

    PEDIDO:
    Matéria-prima: {pedido.residuo_principal}. Escala: {pedido.nivel_producao}.
    {str_ingredientes}
    Objetivo: {objetivo}. 
    
    *** INSTRUÇÃO ***
    Gere OBRIGATORIAMENTE 2 sugestões diferentes.
    
    --- REGRAS ---
    1. NUTRIÇÃO OBRIGATÓRIA: Use os dados do bloco [NUTRIÇÃO]. Se não houver correspondência exata, ESTIME. NUNCA deixe vazio.
    2. LEGISLAÇÃO: Cite TODAS as RDCs/INs específicas encontradas no bloco [LEGISLAÇÃO].
    3. FLUXOGRAMA: Detalhe parâmetros (Temp/Tempo) citados no bloco [CIÊNCIA].
    4. ESCALA: Adapte equipamentos para o nível de produção solicitado.

    --- FORMATO JSON OBRIGATÓRIO ---
    {{
        "resultados": [
            {{
                "nivel": "{pedido.nivel_producao}",
                "nome": "Nome Técnico",
                "pitch": "Resumo...",
                "categoria_visual": "ALIMENTO_SOLIDO",
                "visual_prompt_en": "Description...",
                "validade_estimada": "XX dias",
                "lista_ingredientes": "...",
                "fluxograma": ["1. Recepção", "2. ..."],
                "seguranca": "RDC nº...",
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
                "sustentabilidade": {{ "agua_economizada_litros_100kg": 0 }},
                "economia": {{ "custo_producao_estimado": "R$...", "preco_venda_estimado": "R$..." }},
                "regiao": "Brasil"
            }},
            {{ "nome": "Solução 2", ... }}
        ]
    }}
    """

    messages = [{"role": "system", "content": prompt_sistema}]
    
    if pedido.provedor.lower() == "gemini":
        raw_content = chamar_gemini(messages)
    else:
        raw_content = chamar_principal(messages)

    try: 
        content = json.loads(raw_content)
    except: 
        content = limpar_json(raw_content)
        if not content: raise ValueError("Erro JSON IA")

    lista_final = content.get("resultados", content.get("solucoes", content if isinstance(content, list) else [content]))
    if len(lista_final) > 0 and isinstance(lista_final[0], list): 
        lista_final = lista_final[0]

    return lista_final

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))