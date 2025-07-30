import whisper

def create_model(name="large-v3"):
    model = whisper.load_model(name)
    return model

def wav2txt(model,wav,language="en"):
    result = model.transcribe(wav,language=language)
    return result["text"]