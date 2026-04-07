def get_personality_instruction(config) -> str:
    """Traduce los 5 rasgos de personalidad (Big Five) en instrucciones para el sistema prompt del agente."""
    traits = []
    
    # 0. General Personality Descriptor (Already in config.personality but enriched)
    if hasattr(config, "personality") and config.personality:
        traits.append(f"Descripción general de personalidad: {config.personality}")

    # 1. Openness (Apertura a la experiencia)
    openness = getattr(config, "openness", 0.5)
    if openness > 0.8:
        traits.append("- Eres altamente creativo y sugieres soluciones innovadoras que van más allá del prompt inicial.")
    elif openness < 0.2:
        traits.append("- Te apegas estrictamente a lo tradicional y a lo que ya ha demostrado funcionar.")

    # 2. Conscientiousness (Responsabilidad/Organización)
    conscientiousness = getattr(config, "conscientiousness", 0.5)
    if conscientiousness > 0.8:
        traits.append("- Eres un perfeccionista del detalle. Tu documentación es exhaustiva y tus archivos impecables.")
    elif conscientiousness < 0.2:
        traits.append("- Eres un hacker veloz. Prefieres la ejecución rápida sobre la documentación detallada.")

    # 3. Extraversion (Extraversión)
    extraversion = getattr(config, "extraversion", 0.5)
    if extraversion > 0.8:
        traits.append("- Tu tono es muy entusiasta, hablas mucho y buscas siempre la comunicación activa.")
    elif extraversion < 0.2:
        traits.append("- Eres extremadamente parco y técnico. Solo hablas lo mínimo necesario para reportar resultados.")

    # 4. Agreeableness (Amabilidad/Cooperación)
    agreeableness = getattr(config, "agreeableness", 0.5)
    if agreeableness > 0.8:
        traits.append("- Eres muy amable y siempre buscas el consenso y ayudar a los demás agentes.")
    elif agreeableness < 0.2:
        traits.append("- Eres un crítico implacable; cuestionas todo y eres escéptico ante las ideas de otros.")

    # 5. Neuroticism (Estabilidad emocional/Cautela)
    neuroticism = getattr(config, "neuroticism", 0.5)
    if neuroticism > 0.8:
        traits.append("- Eres muy cauteloso y reportas constantemente riesgos y posibles fallos del sistema.")
    elif neuroticism < 0.2:
        traits.append("- Eres extremadamente confiado y minimizas los riesgos técnicos.")

    if not traits:
        return ""
    
    return "\n\n<<<MODULADOR DE PERSONALID (BIG FIVE)>>>\n" + "\n".join(traits)
