def generate_response(prompt: str) -> dict:
    """
    Return hard-coded responses based on user input keywords.
    Falls back to a default response if no keywords match.
    """
    prompt = prompt.lower()
    response = ""
    if any(word in prompt for word in ["hello", "hi", "hey"]):
        response = "Hello! I'm the QuantumHound assistant. How can I help you plan your time travel adventure today?"

    elif any(word in prompt for word in ["cost", "price", "expensive"]):
        response = "Our time travel packages start at 1 million quantum credits for a basic day trip to the past. Premium packages with extended stays and VIP historical figure meetings are available at higher rates."

    elif any(word in prompt for word in ["safe", "safety", "dangerous"]):
        response = "QuantumHound employs state-of-the-art temporal stabilization technology and has a perfect safety record across all timelines. All travelers are protected by our patented Paradox Prevention Protocol™."

    elif any(word in prompt for word in ["how", "work", "technology"]):
        response = "Our proprietary Quantum Displacement Engine creates stable temporal corridors through the space-time continuum, allowing controlled travel to any point in history. The science is quite complex, but rest assured it's completely safe!"

    elif any(word in prompt for word in ["where", "destination", "visit"]):
        response = "Popular destinations include Ancient Egypt, Renaissance Italy, and the Roaring 20s. We can arrange visits to many time periods, though some restrictions apply to prevent temporal paradoxes."

    else:
        response = "I'm here to help plan your time travel adventure! You can ask about our destinations, safety measures, pricing, or how our technology works."

    return {"success": True, "message": response}
