# import math
# from typing import List, Tuple, Dict
# import torch  # PyTorch
# import torch.nn as nn  # Neural network layers
# import torch.nn.functional as F  # Functional neural network utilities
#
# class PointerNetwork(nn.Module):
#     """Small attention-based Pointer Network that outputs a permutation over tiles.
#
#     Encoder: Processes the input sequence using an RNN (e.g. LSTM) to produce a set of encoder hidden states.
#     Decoder: At each step j, the decoder computes a score u_ij between its current hidden state d_j and the encoder states e_i.
#     embed_dim: The size of the vector used to represent each individual input item (like a coordinate or word) in a continuous space.
#     input_dim: The number of raw features each input element starts with (e.g., 2 for X and Y coordinates in a 2D map).
#     hidden_dim: The number of internal "neurons" or features the model uses to track information as it processes the sequence.
#     batch_first: A setting that tells the model to expect data shaped as (Batch Size, Sequence Length, Features) instead of starting with the sequence length.
#     LSTM: An  RNN layer that processes a sequence and remembers important information.
#     Attention: A mechanism that calculates "scores" to let the decoder decide which specific parts of the input sequence are most important at any given moment.
#     Linear: A standard neural network layer (fully connected) that transforms a vector from one size to another using weights and biases.
#     BiLSTM: Type of RNN that process sequential data in both forward and backward directions using two separate hidden layers.
#     """
#
#     def __init__(self, input_dim: int = 7, embed_dim: int = 96, hidden_dim: int = 128):
#         super().__init__()
#
#         self.input_proj = nn.Linear(input_dim, embed_dim)  # Project raw tile features into the embedding space
#         self.encoder = nn.LSTM(input_dim, embed_dim, batch_first=True, bidirectional=True)  # Encode the tile sequence with a BiLSTM
#
#         # Builds the schedule one step at a time, receives the prev selected tile embedding and the prev decoder hidden state
#         # LSTMCell gives manual control step by step
#         self.decoder_cell = nn.LSTMCell(embed_dim, hidden_dim * 2)  # As we are using BiLSTM, the output size becomes * 2
#
#         # Convert the current decoder hidden state into a query vector
#         self.query_proj = nn.Linear(hidden_dim * 2, hidden_dim * 2, bias=False)
#
#         # Convert each encoder output into a key vector
#         # Keys represent the tiles, Query form the decoder is compared against the keys from all the tiles, helping decide the next best tile
#         self.key_proj = nn.Linear(hidden_dim * 2, hidden_dim * 2, bias=False)
#
#         # Layer turns the combined representation of query and key info into a single scalar score for each tile
#         self.score_proj = nn.Linear(hidden_dim * 2, 1, bias=False)
#
#         # Learnable vector used the decoder's first input before any tile has been selected
#         # Tells the model how to begin the schedule form scratch
#         self.start_token = nn.Parameter(torch.zeros(embed_dim))
#
#     @staticmethod
#     def build_features(
#         tiles: List[Dict],
#         deadlines: List[float],
#         max_deadlines: int = 6
#     ) -> torch.Tensor:  # Convert one sky map into a model input tensor
#         """Build a fixed-width feature tensor from tile dictionaries and deadline ladder."""
#
#         # Keep only finite deadlines and keep at max
#         finite_deadlines = [float(x) for x in deadlines if x != float("inf")]
#         finite_deadlines = finite_deadlines[:max_deadlines]
#
#         # Mark all real deadlines with 1.0.
#         deadline_mask = [1.0] * len(finite_deadlines)
#
#         while len(finite_deadlines) < max_deadlines:  # Pad until the deadline list reaches the fixed model width
#             finite_deadlines.append(0.0)  # Add a zero placeholder for missing deadlines
#             deadline_mask.append(0.0)  # Mark padded deadlines with 0.0 in the mask
#
#         real_deadlines = [value for value in finite_deadlines if value > 0.0]  # Keep only the real +ve deadlines for scaling
#         time_scale = max(real_deadlines) if real_deadlines else 1.0  # Use the largest real deadline as the normalisation scale
#
#         normalised_deadlines = [value / time_scale for value in finite_deadlines]  # Normalise deadlines into 0..1 range
#
#         rows: List[List[float]] = []  # Store one feature vector per tile
#         for tile in tiles:  # Build features for each tile in the sky map
#             ra_deg = float(tile["ra"])
#             dec_deg = float(tile["dec"])
#             prob = float(tile.get("prob", 0.0))
#             dwell = float(tile.get("dwell_time", 60.0))
#
#             ra_rad = math.radians(ra_deg)
#             dec_rad = math.radians(dec_deg)
#
#             row = [  # Tile specific feature vector
#                 math.sin(ra_rad),  # Encode RA using sine so 0 deg and 360 deg stay close
#                 math.cos(ra_rad),  # Encode Ra using cosine for the same circular reasons
#                 math.sin(dec_rad), # Encode Dec using sin & cos
#                 math.cos(dec_rad),
#                 prob,
#                 dwell / max(time_scale, 1.0)  # Normalise dwell tme relative to the scenario horizon
#             ]
#
#             row.extend(normalised_deadlines)  # Added the padded normalised deadline values to every tile
#             rows.append(row)  # Add a mask so the model can tell real deadlines from padded
#
#         return torch.tensor(rows, dtype=torch.float32)
#
#     def forward(self, features: torch.Tensor, target_order: torch.Tensor | None = None) -> Tuple[torch.Tensor, torch.Tensor]: # Run teacher forcing for training and greedy decoding for inference
#         """Return pointer logits and the selected order indices."""
#         if features.dim() == 2:
#             features = features.unsqueeze(0)  # Convert shape from [n, f] to [1, n, f]
#
#         embedded = self.input_proj(features)  # Project the raw features into embedding space
#         encoder_out, _encoder_state = self.encoder(embedded)  # Encode the whole tile list
#
#         # Read the encoded tensor shape:
#             # batch_Size: how many sky maps in this forward pass
#             # seq_len: number of tiles N, also number of decoding steps
#             # hidden_size: size of each encoder output vector at each position
#         batch_size, seq_len, hidden_size = encoder_out.shape
#
#         device = features.device  # Keep all decoder tensors on the same device as the inputs
#         decoder_h = torch.zeros(batch_size, hidden_size, device=device)  # Start the decoder hidden state at zeros
#         decoder_c = torch.zeros(batch_size, hidden_size, device=device)  # Start the decoder cell state at zeros
#
#         # Feed the learned start token at step zero
#         #   unsqueeze: shape goes from [embed_dim] to [1, embed_dim]
#         #   extend: replicates that row for each item in the batch without copying memory where possible (this is the purpose of the -1)
#         decoder_input = self.start_token.unsqueeze(0).expand(batch_size, -1)
#
#         selected_mask = torch.zeros(batch_size, seq_len, dtype=torch.bool, device=device)  # Track which tile positions have already been selected
#
#         logits_per_step: List[torch.Tensor] = []  # Collect logits (a vector of length num_tiles) at each decoding step
#         selections_per_step: List[torch.Tensor] = []  # Collect the chosen tile index at each decoding step
#
#         projected_keys = self.key_proj(encoder_out)  # Pre-project encoder outputs once because they don't change across steps
#
#         for step in range(seq_len):
#             # Update decoder state from the previous selection
#             decoder_h, decoder_c = self.decoder_cell(decoder_input, (decoder_h, decoder_c))
#
#             # Project the decoder hidden state into query space
#             query = self.query_proj(decoder_h).unsqueeze(1) # Adds a middle dim so shape is convenient for broadcasting when adding to projected_keys
#
#             # Combine the decoder query with all encoder keys
#             #   For each batch row, the single query vector is added to every tile's key vector
#             #   tanh squashes activations to (-1,1)
#             energy = torch.tanh(query + projected_keys) # Additive-attention pattern
#
#             # Convert the attention activations into one score per tile
#             step_logits = self.score_proj(energy).squeeze(-1)  # remove last dim -> [batch, seq_len]
#
#             # Prevent the decoder from selecting the same time twice
#             #   masked_fill: where selected_mask is True, set logit to -inf
#             #   after a softmax, -inf becomes probability 0, so tile can't be chosen again, making the output a permutation (no repeats)
#             step_logits = step_logits.masked_fill(selected_mask, float("-inf"))
#
#             logits_per_step.append(step_logits)  # Stores the raw scores for cross-entropy loss calculation
#
#             # Teacher forcing vs greedy inference
#             if target_order is not None:  # Use Teacher forcing during training if the gold permutation is provided
#                 chosen_index = target_order[:, step]  # Follow the label order at this decoding step
#             else:  # Perform greedy inference for fast scheduling
#                 chosen_index = torch.argmax(step_logits, dim=1)  # Select the highest-scoring unused tile
#
#             selections_per_step.append(chosen_index)  # Save the chosen tile index for output
#             selected_mask.scatter_(1, chosen_index.unsqueeze(1), True)  # Mark the chosen tile as -inf for later steps
#
#             # Build the gather index for the chosen embedded tile
#             gather_index = chosen_index.view(batch_size, 1, 1).expand((-1, 1, embedded.size(-1)))
#
#             # Feed the chosen tile embedding into the next decoder step
#             #   along dim=1, pick the embedding for chosen_index
#             #   remove the middle dimension -> [batch, embd_dim]
#             decoder_input = embedded.gather(1, gather_index).squeeze(1) # This embedding becomes the input to the next LSTMCell
#
#         # Stack logits into shape [batch, steps, seq_len]
#         stacked_logits = torch.stack(logits_per_step, dim=1)
#
#         # Stack chosen indices into shape [batch, steps]
#         stacked_indices = torch.stack(selections_per_step, dim=1)
#
#         return stacked_logits, stacked_indices
#
#     def predict_order(self, tiles: List[Dict], deadlines: List[float], device: str = "cpu") -> List[int]:
#         """Run greedy inference and return an ordered list of tile indices."""
#         self.eval()  # Switch model to evaluation mode
#         with torch.no_grad():  # Disable gradient tracking for fast inference
#             features = self.build_features(tiles=tiles, deadlines=deadlines).to(device)  # Build & move the input features
#             _logits, indices = self.forward(features, target_order=None) # Decode a full permutation greedily
#
#             return [int(x) for x in indices[0].tolist()]  # Convert the first batch item into a list
#
# def pointer_loss(step_logits: torch.Tensor, target_order: torch.Tensor) -> torch.Tensor:
#     """Compute the mean cross-entropy loss across decoder steps"""
#     batch_size, steps, seq_len = step_logits.shape  # Read the pointer logit tensor shape
#     flat_logits = step_logits.reshape(batch_size * steps, seq_len)  # Flatten steps into the batch dimension
#     flat_target = target_order.reshape(batch_size * steps)
#     return F.cross_entropy(flat_logits, flat_target)  # Averaged multi-class cross-entropy
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
#
