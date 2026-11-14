import requests

API_URL = "https://evolution-api-production-f0aee.up.railway.app"
API_KEY = "*#Inflaboom2026#*" 
INSTANCE = "inflaboom"
HEADERS = {"apikey": API_KEY}

print("Solicitando un QR nuevo al servidor...")
res = requests.get(f"{API_URL}/instance/connect/{INSTANCE}", headers=HEADERS)
data = res.json()

qr_base64 = data.get('base64') or (data.get('qrcode', {}).get('base64') if isinstance(data.get('qrcode'), dict) else data.get('qrcode'))

if qr_base64:
    # Reparar el formato de la imagen para que el navegador la lea
    if not qr_base64.startswith("data:image"):
        qr_base64 = "data:image/png;base64," + qr_base64
        
    html = f"<div style='text-align:center; font-family:sans-serif; margin-top:50px;'><h2>Escanea rápido (Expira en 40 seg)</h2><img src='{qr_base64}' style='width:350px; border:2px solid #ccc; border-radius:10px; padding:10px;'></div>"
    with open("qr.html", "w", encoding="utf-8") as f: 
        f.write(html)
    
    print("¡Listo! Ve a la pestaña de tu navegador donde está el cuadro blanco y presiona F5.")
else:
    print("El servidor no devolvió el QR. Esto suele pasar si el WhatsApp YA está conectado. Respuesta:", data)