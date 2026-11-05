"""
Voogle Voice Integration Module
Handles incoming telephony webhooks (compatible with Twilio, Africa's Talking, 
and standard IVR gateways), routes transcribed speech through the Gemini AI 
pipeline, and returns synthesized voice responses.
"""

import os
import logging
from flask import Blueprint, request, Response
import google.generativeai as genai

logger = logging.getLogger(__name__)

voice_bp = Blueprint('voice', __name__)

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel('gemini-pro')

@voice_bp.route('/voice/incoming', methods=['POST'])
def incoming_call():
    """
    Webhook triggered when a user dials the Voogle phone number.
    Greets the user and prompts them to record their query.
    """
    # Standard IVR XML response (compatible with Twilio / Africa's Talking voice APIs)
    xml_response = """<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say>Welcome to Voogle. Please state your question or request after the beep.</Say>
        <Record action="/voice/callback" method="POST" maxLength="30" transcribe="true" />
    </Response>
    """
    return Response(xml_response, mimetype='application/xml')

@voice_bp.route('/voice/callback', methods=['POST'])
def voice_callback():
    """
    Handles the completed voice recording and provider-side transcription,
    processes the input with Gemini AI, and responds with synthesized speech.
    """
    caller_number = request.form.get('From', 'Unknown')
    # Captures transcription text from telephony providers that support auto-transcription
    user_query = request.form.get('TranscriptionText') or request.form.get('SpeechResult', '')

    logger.info(f"Received voice interaction from {caller_number}: {user_query}")

    if not user_query:
        fallback_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say>Sorry, we could not detect your voice input. Please try calling again.</Say>
            <Hangup/>
        </Response>
        """
        return Response(fallback_xml, mimetype='application/xml')

    try:
        # Pass the transcribed query into the Gemini AI pipeline optimized for voice responses
        prompt = (
            "You are Voogle, an assistant providing concise information via phone calls "
            "for low-resource feature phone users. Keep answers brief, clear, and easy to listen to. "
            f"User query: {user_query}"
        )
        ai_response = gemini_model.generate_content(prompt)
        response_text = ai_response.text.strip()
    except Exception as e:
        logger.error(f"Gemini voice processing error: {e}")
        response_text = "Sorry, Voogle is currently unable to process your request. Please try again later."

    # Return XML instruction to read the Gemini response back to the caller
    response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say>{response_text}</Say>
        <Hangup/>
    </Response>
    """
    return Response(response_xml, mimetype='application/xml')
