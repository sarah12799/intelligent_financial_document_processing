
🧾 Intelligent Financial Document Processing
Automating financial data extraction and validation with AI + LLMs

Finance teams often spend hours copying balances, accounts, and credits from PDFs or Excel files. The process is slow, error-prone, and delays timely, data-driven decisions.
 This project is a prototype of an intelligent extraction application that automates this workflow while ensuring reliability through a validation & correction interface.

✨ Key Features

🤖 AI-powered extraction: balances, debits, credits, accounts, prior balances


📝 Document ↔ editable table view: fast human validation & correction


🔄 Continuous learning: corrections stored to retrain and improve models


🗄 Traceability: every edit is logged for audit and future model refinement


🏗️ Architecture

Ingestion (PDF) 
     ↓
Extraction (pdfplumber, Regex, GPT-4 prompts) 
     ↓
Validation UI (Flask + HTML/CSS/JS) 
     ↓
Correction Storage (MongoDB: files, edits, vectors) 
     ↓
Retrieval & Continuous Improvement (LangChain + Embeddings)

![1756912708556](https://github.com/user-attachments/assets/49f8d0b8-e694-43eb-9bdd-d01e51cc6239)



⚙️ Tech Stack

Backend & Prototype UI: Flask, HTML/CSS/JavaScript


Extraction: pdfplumber, Regex, GPT-4 contextual prompts


AI & Similarity: LangChain, OpenAI Embeddings, Cosine Similarity


Database: MongoDB (documents, corrections, history, vectors)


🚀 Demo Screenshots
<img width="1347" height="584" alt="Capture d'écran 2025-09-03 161107" src="https://github.com/user-attachments/assets/79fdf31e-43c3-4307-851a-cfde8f5db274" />


📚 What I Learned
Designing LLM + vector database architectures for continuous improvement


Building robust ingestion → extraction → correction pipelines


Balancing automation with human validation in critical financial workflows


Hands-on experimentation with RAG pipelines and document AI



🔮 Next Steps
Improve model accuracy with fine-tuned LayoutLM or similar document AI


Add React/Angular frontend for a richer user experience


Expand to multi-format financial documents


🧑‍💻 Author
Sarra Tlili
 Computer Engineering Student | AI & Business Intelligence Enthusiast
🌐 LinkedIn


💻 GitHub




