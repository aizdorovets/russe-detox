import math
import json
import pathlib
from typing import Optional

import torch
from torch import nn
from torch.utils.data import DataLoader
import transformers
from transformers.optimization import (
    get_linear_schedule_with_warmup,
    Optimizer,
)
from tqdm import tqdm

from utils.metrics import Averagetron


class Trainer3000(transformers.Trainer):

    def __init__(
        self,
        model: nn.Module,
        train_loader: DataLoader,
        val_loader: Optional[DataLoader] = None,
        output_dir: str = './checkpoints',
        overwrite_output_dir: bool = False,
        save_every_n_steps: int = 10,
        optimizer: Optional[Optimizer] = None,
        lr_schedule: str = 'linear',
        max_epochs: int = 69,
        learning_rate: float = 3e-4,
        warmup_ratio: float = 0.0,
        gradient_accumulation_steps: int = 1,
    ):
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.output_dir = output_dir
        self.overwrite_output_dir = overwrite_output_dir
        self.save_every_n_steps = save_every_n_steps
        self.optimizer = optimizer
        self.max_epochs = max_epochs
        self.learning_rate = learning_rate
        self.warmup_ratio = warmup_ratio
        self.gradient_accumulation_steps = gradient_accumulation_steps
        self.lr_scheduler = self._get_lr_scheduler(lr_schedule)

        # Attributes
        self.epoch = 0
        self.global_step = 0

    def run(self):
        self.model.train()
        min_val_loss = 0
        for epoch in range(self.max_epochs):
            train_loss, train_lr = self._train()
            # Validation
            if self.val_loader:
                val_loss = self._validate()
                # Checkpoint
                if val_loss < min_val_loss:
                    self._save_checkpoint()
            else:
                # Checkpoint
                if (epoch + 1) % self.save_every_n_steps == 0:
                    self._save_checkpoint()

    def _get_lr_scheduler(self, lr_schedule):
        num_steps = math.ceil(len(self.train_loader) * self.max_epochs / self.gradient_accumulation_steps)
        num_warmups_steps = math.floor(num_steps * self.warmup_ratio)
        if lr_schedule == 'linear':
            self.lr_scheduler = get_linear_schedule_with_warmup(
                self.optimizer,
                num_warmup_steps=num_warmups_steps,
                num_training_steps=num_steps,
                )
        else:
            raise NotImplementedError('Only linear schedule is implemented atm.')

    def _train(self):
        averaged_loss = Averagetron()
        for batch_idx, batch in tqdm(enumerate(self.train_loader), leave=False):
            # Training step
            output = self.model(**batch)
            loss = output.loss / self.gradient_accumulation_steps
            loss.backward()
            # Gradient accumulation
            if (batch_idx + 1) % self.gradient_accumulation_steps == 0 or \
                    batch_idx + 1 == len(self.train_loader):
                self.optimizer.step()
                self.lr_scheduler.step()
                self.optimizer.zero_grad()
            averaged_loss.update(loss.item())
        return averaged_loss.compute(), self.lr_scheduler.get_last_lr()[0]

    def _validate(self):
        self.model.eval()
        averaged_loss = Averagetron()
        with torch.no_grad():
            for batch_idx, batch in tqdm(enumerate(self.train_loader), leave=False):
                output = self.model(**batch)
                loss = output.loss
                averaged_loss.update(loss.item())
        return averaged_loss.compute()

    def _save_checkpoint(self):
        pathlib.Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(self.output_dir)
        state = {
            'epoch': self.epoch,
            'global_step': self.global_step,
        }
        with open(f'{self.output_dir}/state.json', 'w', encoding='utf8') as f:
            json.dump(state, f)
