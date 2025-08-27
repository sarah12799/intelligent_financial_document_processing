import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from services.utils import clean_json_output

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("⚠️ OPENAI_API_KEY manquant dans .env")

client = OpenAI(api_key=api_key)

def build_prompt(tokens_dict):
    table_str = "\n".join([f"{tid}: {txt}" for tid, txt in tokens_dict.items()])
    return f"""
Tu es un assistant expert en analyse comptable.

On te donne une liste de tokens extraits d'un document PDF :
{table_str}

Ta mission :
1. Identifier les lignes comptables dans l'ordre exact où elles apparaissent dans les tokens.
2. Retourner UNIQUEMENT un JSON valide, sous forme de liste d'objets.
3. Chaque objet JSON doit contenir les champs suivants : compte, solde_an, solde, débit, crédit.
4. Pour chaque champ :
   - Si une valeur est trouvée, retourne un tableau [valeur, id] où 'valeur' est la valeur extraite et 'id' est l'identifiant du token correspondant.
   - Si la valeur est absente, retourne [null, null].
5. Pour les champs débit et crédit :
   - Si aucune valeur n'est présente, retourne [0, null].
6. Respecte strictement ce format pour chaque champ, sans exception.
7. Ne modifie pas l'ordre des lignes comptables détectées.
"""
def process_tokens(tokens_dict, model="gpt-4-0125-preview"):
    prompt = build_prompt(tokens_dict)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Tu es un assistant intelligent d’extraction comptable."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    content = response.choices[0].message.content.strip()
    cleaned = clean_json_output(content)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "Format JSON invalide", "raw": cleaned}
