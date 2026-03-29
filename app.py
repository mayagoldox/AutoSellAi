import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from flask import Flask, request, jsonify
import stripe
from openai import OpenAI
from fpdf import FPDF
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Your Custom AI Money-Making Blueprint', 0, 1, 'C')
        self.ln(10)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf(content, niche):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', size=12)
    lines = content.split('\n')
    for line in lines:
        pdf.multi_cell(0, 8, line.encode('latin-1', 'replace').decode('latin-1'))
        if pdf.get_y() > 270:
            pdf.add_page()
    filename = f"blueprint_{niche.replace(' ', '_')}.pdf"
    pdf.output(filename)
    return filename

def send_email(to_email, pdf_path, niche):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = to_email
    msg['Subject'] = f"Your Custom AI Blueprint for {niche} is Ready!"
    body = "Thank you for your purchase!\n\nYour personalized AI Money-Making Blueprint is attached.\n\nStart implementing today and watch your income grow!\n\n- AutoSellAI Team"
    msg.attach(MIMEText(body, 'plain'))
    with open(pdf_path, "rb") as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename={os.path.basename(pdf_path)}")
        msg.attach(part)
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(EMAIL_USER, EMAIL_PASS)
    server.send_message(msg)
    server.quit()
    os.remove(pdf_path)

@app.route('/')
def home():
    return '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>AutoSellAI</title><style>body{font-family:Arial,sans-serif;max-width:800px;margin:40px auto;text-align:center;}h1{color:#00cc66;}input,button{padding:15px;margin:10px;font-size:18px;}button{background:#00cc66;color:white;border:none;cursor:pointer;}</style></head><body><h1>Instant Custom AI Money-Making Blueprint</h1><p><strong>Only $47 - Delivered in seconds - 100% Personalized</strong></p><p>Tell us your niche and get a complete step-by-step eBook on how to make money with AI in that exact field.</p><form id="checkout-form"><input type="text" id="niche" placeholder="Your niche (e.g. fitness, real estate, dropshipping)" required style="width:80%;"><br><input type="email" id="customer_email" placeholder="Your email address" required style="width:80%;"><br><button type="button" onclick="createCheckout()" style="width:80%;font-size:22px;padding:20px;">BUY NOW - ONLY $47</button></form><script>async function createCheckout(){const niche=document.getElementById("niche").value.trim();const email=document.getElementById("customer_email").value.trim();if(!niche||!email)return alert("Please fill both fields");const response=await fetch("/create-checkout-session",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({niche,customer_email:email})});const data=await response.json();if(data.url)window.location.href=data.url;else alert("Error: "+data.error);}</script></body></html>'''

@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    data = request.get_json()
    niche = data.get('niche')
    customer_email = data.get('customer_email')
    
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price_data': {'currency': 'usd', 'product_data': {'name': f'Custom AI Blueprint - {niche}'}, 'unit_amount': 4700}, 'quantity': 1}],
            mode='payment',
            customer_email=customer_email,
            success_url='http://localhost:5000/success',
            cancel_url='http://localhost:5000/cancel',
            metadata={'niche': niche, 'customer_email': customer_email}
        )
        return jsonify({'url': session.url})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/success')
def success():
    return '<h1 style="color:green;text-align:center;margin-top:100px;">Payment successful! Your custom blueprint is being generated and emailed right now.</h1>'

@app.route('/cancel')
def cancel():
    return '<h1 style="text-align:center;margin-top:100px;">Payment cancelled. No charge was made.</h1>'

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        niche = session['metadata']['niche']
        customer_email = session['metadata']['customer_email']
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": f"Generate a detailed, professional, 3000+ word e-book titled AI Money-Making Blueprint for the {niche} niche. Structure: Introduction, 5 Proven Strategies, Must-Have AI Tools, Real Case Studies, Step-by-Step 30-Day Action Plan, Common Mistakes and How to Avoid Them, Conclusion. Make it actionable, exciting, and ready to implement immediately."}]
            )
            content = response.choices[0].message.content
            pdf_path = generate_pdf(content, niche)
            send_email(customer_email, pdf_path, niche)
        except Exception as e:
            print("Generation error:", e)
    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
