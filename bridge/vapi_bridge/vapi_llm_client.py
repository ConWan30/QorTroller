import os
import requests
from dotenv import load_dotenv

class QorTrollerAI:
    def __init__(self):
        # Load environment variables from bridge/.env (relative to this file)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.abspath(os.path.join(current_dir, "..", ".env"))
        load_dotenv(env_path)

        # Also load from root .env if it exists in parent path
        root_env_path = os.path.abspath(os.path.join(current_dir, "..", "..", ".env"))
        load_dotenv(root_env_path)

        # Load API key, fallback to provided key if not set
        self.api_key = os.environ.get("QUICKSILVER_API_KEY")
        if not self.api_key:
            self.api_key = "sk-el_TumeRtoQdi-lY-YQmTQ"

    def _post_completion(self, system_prompt, user_content):
        url = "https://api.quicksilverpro.io/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-v4-flash",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
        }
        try:
            # Bypassing local proxies to prevent DNS resolution errors
            response = requests.post(
                url, 
                headers=headers, 
                json=payload, 
                proxies={"http": None, "https": None}
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"API Connection Error: {e}")
            return None

    def evaluate_session_integrity(self, pitl_telemetry_dict):
        """
        Takes the full L0-L9 sensor outputs and acts as the final judge
        on human liveness and hardware spoofing.
        """
        system_prompt = (
            "You are the Final Integrity Judge for the QorTroller V.A.P.I. protocol. "
            "Analyze the provided L0-L9 sensor telemetry dictionary for signs of hardware spoofing, "
            "botting, or macro automation. Provide a definitive verdict on human liveness and session integrity."
        )
        user_content = (
            f"Analyze this full L0-L9 sensor telemetry dictionary for session integrity and human liveness. "
            f"Telemetry: {pitl_telemetry_dict}"
        )
        return self._post_completion(system_prompt, user_content)

    def generate_scouting_report(self, vhr_replay_data):
        """
        Takes Arc 5 verified human replay data and profiles the player's
        intent, skill, and playstyle for the data marketplace.
        """
        system_prompt = (
            "You are the Player Profiling Engine for the QorTroller V.A.P.I. data marketplace. "
            "Analyze the provided Arc 5 verified human replay data and generate a scouting report "
            "profiling the player's intent, skill level, and playstyle."
        )
        user_content = (
            f"Generate a detailed scouting report profiling the player's playstyle, intent, and skill level "
            f"based on this verified human replay data: {vhr_replay_data}"
        )
        return self._post_completion(system_prompt, user_content)

    def generic_chat(self, system_prompt, user_data):
        """
        A flexible method so any new QorTroller module can easily call the AI.
        """
        user_content = str(user_data)
        return self._post_completion(system_prompt, user_content)

    def chat(self, messages, model="deepseek-v4-flash"):
        """
        Sends a full list of messages (conversation history) to the API for multi-turn chat.
        """
        url = "https://api.quicksilverpro.io/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages
        }
        try:
            response = requests.post(
                url, 
                headers=headers, 
                json=payload, 
                proxies={"http": None, "https": None}
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"API Connection Error: {e}")
            return None
