from model_base import ModelBase
from functools import partial
import torch

class ModelGeneration(ModelBase):
    def __init__(self, model_nickname: str):
        super().__init__(model_nickname)

        self.hooks = []
        self._register_hooks()
        self.perturbation = None

    def set_perturbation(self, perturbation):
        self.perturbation = perturbation

    def _register_hooks(self):
        def _hook_fn(module, input, output, layer_idx):
            if self.perturbation is not None:
                output = self.perturbation.get_perturbation(output, layer_idx)
            return output
        
        for i in range(self.llm_cfg.n_layer):
            layer = self.model.model.layers[i]
            hook = layer.register_forward_hook(partial(_hook_fn, layer_idx=i))
            self.hooks.append(hook)

    def generate(self, prompt: str, max_length: int=1000, output_hidden_states: bool=True) -> dict:
        prompt = self.apply_inst_template(prompt)
        input_ids = self.tokenizer.apply_chat_template(prompt, add_generation_prompt=True, return_tensors="pt").to(self.device)

        terminators = [
            self.tokenizer.eos_token_id,
            self.tokenizer.convert_tokens_to_ids("<|eot_id|>"),
        ]

        input_token_number = input_ids.size(1)

        output = self.model.generate(
            input_ids,
            max_length=max_length,
            output_hidden_states=output_hidden_states,
            return_dict_in_generate=True,
            eos_token_id=terminators,
            do_sample=False,
        )

        result = {
            "completion_token_number": output.sequences[0].size(0) - input_token_number,
            "completion": self.tokenizer.decode(output.sequences[0][input_token_number:], skip_special_tokens=True),
        }

        if output_hidden_states:
            result["hidden_states"] = output.hidden_states

        return result
    
    def __del__(self):
        for hook in self.hooks:
            hook.remove()