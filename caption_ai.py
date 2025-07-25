import openai
import os

# You can also load this from a secure .env file
openai.api_key = os.getenv("OPENAI_API_KEY", "your-api-key")

def suggest_caption(prompt_text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a creative social media assistant who writes short, catchy post captions."},
                {"role": "user", "content": f"Suggest a caption for this post: {prompt_text}"}
            ]
        )
        return response.choices[0].message["content"].strip()
    except Exception as e:
        return f"Error generating caption: {e}"
