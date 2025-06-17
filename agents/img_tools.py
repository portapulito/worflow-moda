from google.adk.tools import ToolContext
from google.genai import types
import requests
import urllib.parse
from pathlib import Path
import time

async def download_and_save_image_auto_tool(
    tool_context: ToolContext,
    image_url: str
) -> dict:
    """
    Tool per scaricare e salvare immagini con versioning automatico incrementale.
    Usa lo stesso filename per tutte le immagini per sfruttare il versioning nativo di ADK.
    
    Args:
        tool_context: Contesto del tool fornito da ADK
        image_url: URL dell'immagine da scaricare
    
    Returns:
        dict: Risultato dell'operazione con status, filename, version incrementale e messaggi
    """
    try:
        # Normalizza l'URL per controlli consistenti
        normalized_url = image_url.strip()
        
        # Inizializza lo state per le immagini salvate se non esiste
        if "saved_images_by_url" not in tool_context.state:
            tool_context.state["saved_images_by_url"] = {}
        if "download_order" not in tool_context.state:
            tool_context.state["download_order"] = []
        if "all_versions" not in tool_context.state:
            tool_context.state["all_versions"] = []
        
        saved_images = tool_context.state["saved_images_by_url"]
        
        # Controlla se questo URL specifico è già stato processato
        if normalized_url in saved_images:
            existing = saved_images[normalized_url]
            return {
                "status": "already_exists",
                "filename": existing["filename"],
                "version": existing["version"],
                "url": image_url,
                "message": f"Immagine da questo URL già salvata come '{existing['filename']}' (versione {existing['version']})"
            }
        
        # Download dell'immagine
        print(f"Scaricando immagine da: {image_url}")
        response = requests.get(image_url, timeout=30, headers={'User-Agent': 'ADK-ImageTool/1.0'})
        response.raise_for_status()
        
        # Determina il tipo MIME e l'estensione
        content_type = response.headers.get('content-type', 'image/jpeg')
        if 'image' not in content_type:
            return {
                "status": "error",
                "message": f"L'URL non punta a un'immagine valida. Content-Type: {content_type}"
            }
        
        # Determina l'estensione dal content-type
        ext_map = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg', 
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'image/svg+xml': '.svg'
        }
        extension = ext_map.get(content_type, '.jpg')
        
        # USA FILENAME FISSO per versioning automatico ADK
        base_filename = f"downloaded_images{extension}"
        
        # Crea Part con i dati binari
        image_part = types.Part.from_bytes(
            data=response.content,
            mime_type=content_type
        )
        
        # Salva con STESSO filename per versioning incrementale automatico
        version = await tool_context.save_artifact(
            filename=base_filename,
            artifact=image_part
        )
        
        # Calcola ordine di download
        download_order = len(tool_context.state["download_order"]) + 1
        tool_context.state["download_order"].append(normalized_url)
        
        # Aggiorna lo state con informazioni dettagliate
        saved_images[normalized_url] = {
            "filename": base_filename,
            "version": version,
            "url": image_url,
            "original_url": image_url,
            "content_type": content_type,
            "size_bytes": len(response.content),
            "download_order": download_order,
            "timestamp": int(time.time())
        }
        
        # Traccia tutte le versioni per accesso futuro
        version_info = {
            "filename": base_filename,
            "version": version,
            "url": image_url,
            "download_order": download_order,
            "content_type": content_type,
            "size_bytes": len(response.content),
            "timestamp": int(time.time())
        }
        tool_context.state["all_versions"].append(version_info)
        
        # Aggiorna statistiche globali
        tool_context.state["images_total_count"] = len(saved_images)
        tool_context.state["images_total_size"] = sum(
            img_data["size_bytes"] for img_data in saved_images.values()
        )
        
        return {
            "status": "success",
            "filename": base_filename,
            "version": version,
            "url": image_url,
            "content_type": content_type,
            "size_bytes": len(response.content),
            "download_order": download_order,
            "total_images": len(saved_images),
            "total_versions": len(tool_context.state["all_versions"]),
            "message": f"✅ Immagine #{download_order} salvata come '{base_filename}' versione {version} - Totale versioni: {len(tool_context.state['all_versions'])}"
        }
        
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Errore nel download: {str(e)}",
            "url": image_url
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Errore imprevisto: {str(e)}",
            "url": image_url
        }


async def download_multiple_images_tool(
    tool_context: ToolContext,
    image_urls: str
) -> dict:
    """
    Tool per scaricare multiple immagini con versioning incrementale automatico.
    Tutti gli URLs vengono salvati con lo stesso filename per sfruttare il versioning nativo di ADK.
    
    Args:
        tool_context: Contesto del tool fornito da ADK
        image_urls: URLs separati da virgola (es: "url1,url2,url3")
    
    Returns:
        dict: Risultato del batch download con versioning incrementale
    """
    try:
        # Parsing intelligente degli URLs
        if ', ' in image_urls:
            urls_list = [url.strip() for url in image_urls.split(', ') if url.strip()]
        elif ' ' in image_urls and ',' not in image_urls:
            urls_list = [url.strip() for url in image_urls.split() if url.strip() and url.startswith('http')]
        else:
            parts = [part.strip() for part in image_urls.split(',')]
            urls_list = []
            i = 0
            while i < len(parts):
                part = parts[i]
                if part.startswith('http'):
                    while i + 1 < len(parts) and not parts[i + 1].startswith('http'):
                        i += 1
                        part += ',' + parts[i]
                    urls_list.append(part)
                i += 1
        
        if not urls_list:
            return {
                "status": "error",
                "message": "Nessun URL valido fornito"
            }
        
        results = []
        successful_downloads = 0
        errors = []
        
        for i, url in enumerate(urls_list, 1):
            print(f"Processando URL {i}/{len(urls_list)}: {url}")
            
            try:
                # Usa il tool automatico per ogni URL (che ora usa versioning)
                result = await download_and_save_image_auto_tool(tool_context, url)
                results.append(result)
                
                if result["status"] == "success" or result["status"] == "already_exists":
                    successful_downloads += 1
                else:
                    errors.append(f"URL {i}: {result.get('message', 'Errore sconosciuto')}")
                    
            except Exception as e:
                error_msg = f"URL {i} ({url}): {str(e)}"
                errors.append(error_msg)
                results.append({
                    "status": "error",
                    "url": url,
                    "message": str(e)
                })
        
        # Statistiche finali con informazioni versioning
        total_images = tool_context.state.get("images_total_count", 0)
        total_size = tool_context.state.get("images_total_size", 0)
        all_versions = tool_context.state.get("all_versions", [])
        
        # Calcola range di versioni
        successful_results = [r for r in results if r.get("status") == "success"]
        if successful_results:
            versions = [r.get("version", 0) for r in successful_results]
            version_range = f"{min(versions)}-{max(versions)}" if len(versions) > 1 else str(versions[0])
        else:
            version_range = "N/A"
        
        return {
            "status": "success" if successful_downloads > 0 else "error",
            "processed_urls": len(urls_list),
            "successful_downloads": successful_downloads,
            "errors_count": len(errors),
            "total_images_in_session": total_images,
            "total_size_bytes": total_size,
            "version_range": version_range,
            "total_versions_saved": len(all_versions),
            "base_filename": "downloaded_images.jpg",
            "versioning_mode": "INCREMENTALE_ATTIVO",
            "results": results,
            "errors": errors if errors else None,
            "message": f"🎯 VERSIONING INCREMENTALE: {successful_downloads} nuove immagini salvate! Versioni: {version_range}. TOTALE VERSIONI: {len(all_versions)}"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Errore nel processamento batch: {str(e)}"
        }







