class BaseAIProvider:
    def generate_content(self, prompt: str, **kwargs) -> str:
        """
        Generate text content based on the provided prompt.
        
        Args:
            prompt: The text prompt to send to the model.
            **kwargs: Additional configuration parameters (e.g. temperature, max_tokens).
            
        Returns:
            The generated response string.
        """
        raise NotImplementedError("Subclasses must implement generate_content")
