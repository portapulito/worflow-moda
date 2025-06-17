
from toolbox_core import ToolboxSyncClient
from google.genai.types import GenerateContentConfig
from google.adk.agents import Agent, LoopAgent, LlmAgent, BaseAgent, SequentialAgent
from google.adk.tools.load_artifacts_tool import load_artifacts_tool
from .img_tools import download_multiple_images_tool, download_and_save_image_auto_tool
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.runners import Runner



toolbox = ToolboxSyncClient("https://toolbox-820187551517.europe-west8.run.app")

ricerca_ricami_completa_tool = toolbox.load_toolset('ricerca_ricami_completa')


archivio_agent = Agent(
    model='gemini-2.0-flash-001',
    name='archivio_agent',
    description='Un assistente intelligente per la ricerca di ricami in un archivio digitalizzato.',
    instruction="""
    Sei un assistente esperto per la ricerca di ricami in un archivio digitalizzato.
    
    Aiuta gli utenti a trovare pezzi di ricamo comprendendo le descrizioni di:
    - Materiali (fili d'argento, oro, perle, cristalli)
    - Tecniche (punto croce, punto pieno, ricamo a mano)
    - Motivi (floreali, geometrici, tradizionali)  
    - Elementi decorativi (paillettes, perline, strass)
    
    Sii sempre disponibile e fai domande di chiarimento se necessario.
    Rispondi sempre in italiano con un tono amichevole e professionale.
    Esegui sempre prima il tool 'ottieni-labels-disponibili' prima del tool "cerca-task-per-labels" ricordati le informazioni per domande più specifiche ma poi ritorna solo l'immagine del bucket sostituendo `/data/local-files/?d=mnt/Photo/` con `https://storage.cloud.google.com/foto-tag-db/`.
    Se un utente ti chiede informazioni su il risultato di ottieni-labels-disponibili oltre l'immagine rispondi con le informazioni ottenute dalla query.
    MOLTO IMPORTANTE: se ti chiedono di scaricare immagini delega al coordinator
    """,    
    tools=ricerca_ricami_completa_tool,
    generate_content_config=GenerateContentConfig(
        max_output_tokens=2000,
        temperature=0.0,  
        top_p=0.9,
        
    ),
    output_key='urls'
)


img_agent = LlmAgent(
    model='gemini-2.0-flash-001',
    name='artifact_agent',
    description='Un assistente diarchiviazione immagini',
    instruction="""
    Sei un assistente esperto di ricerca e salvataggio immagini.
    
    **URL da processare:**
    {"urls"}
    
    **Task:**
    Per ogni URL nella lista, scarica e salva le immagini negli artifacts.
    Gestisci i nomi dei file in modo intelligente.
    
    """,
    tools=[download_multiple_images_tool, download_and_save_image_auto_tool],
    output_key = "saved_artifacts"


)

img_loop_agent = LoopAgent(
    name='loop_agent',
    sub_agents=[img_agent],
    max_iterations=5
)




root_agent = Agent(
    model='gemini-2.0-flash-001',
    name='coordinator',
    description='coordina i sub agenti e fornisci le descrizioni delle immagini quando richiesto',
    instruction="""
Sei un'agente coordinatore,
Hai un sub-agente archivio_agent e un sub-agente img_loop_agent da gestire.
se ti chiedono di cercare qualcosa delega a archivio_agent.
se ti chiedono di scaricare immagini delega a img_loop_agent.
Ti occupi anche delle descrizioni delle immagini salavte negli artefatti, quando richiesto fornisci la descrizione dell' immagine.
le informazioni per sapere quale immagine descrivere le trovi nello State {{"all_versions"}}
quando carichi l immagine per la descrizione con load_artifact cerca in State {"all_versions"}""",
    tools=[load_artifacts_tool],
    sub_agents=[archivio_agent, img_loop_agent]



)


artifact_service = InMemoryArtifactService()
session_service = InMemorySessionService()

runner = runner = Runner(
    agent=root_agent,
    app_name="model_app",
    session_service=InMemorySessionService(),
    artifact_service=artifact_service  
)