"""
question_generator.py
Generates age-appropriate math questions for all 3 levels,
constrained by the current AdaptiveConfig.
"""

import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from adaptive_engine import AdaptiveConfig


@dataclass
class Question:
    level: int
    prompt: str              # Text shown / spoken (e.g., "Find a number > 7")
    operator: str            # '>', '<', '=', '+', '-', 'chain'
    target: int              # The answer the child must reach / collect
    operands: List[int]      # Numbers the child must touch (in order)
    distractors: List[int]   # Wrong numbers also shown
    hint: str                # Coaching hint shown after failure
    audio_prompt: str        # TTS-friendly string


class QuestionGenerator:
    """
    Factory that builds Question objects for each level.
    """

    def __init__(self, config: AdaptiveConfig):
        self.config = config

    def update_config(self, config: AdaptiveConfig):
        self.config = config

    # ------------------------------------------------------------------ #
    #  Level 1 – Comparison                                               #
    # ------------------------------------------------------------------ #

    def level1(self) -> Question:
        """
        Ask the child to find a number that is >, <, or = to a reference.
        Correct answer: any one valid number from the floating pool.
        """
        cfg       = self.config
        operator  = random.choice(['>', '<', '='])
        reference = random.randint(1, max(2, cfg.max_operand - 1))

        # Build the pool of correct answers
        if operator == '>':
            correct_pool = list(range(reference + 1, cfg.max_operand + 10))
            op_word      = "greater than"
        elif operator == '<':
            correct_pool = list(range(1, reference))
            op_word      = "less than"
        else:
            correct_pool = [reference]
            op_word      = "equal to"

        if not correct_pool:
            correct_pool = [reference + 1] if operator == '>' else [1]

        target     = random.choice(correct_pool[:min(len(correct_pool), 8)])
        operands   = [target]
        distractors = self._safe_distractors(operands, cfg.distractor_count,
                                              lo=1, hi=cfg.max_operand + 10,
                                              exclude_fn=lambda x: _matches_op(x, operator, reference))

        prompt = f"Touch a number {op_word} {reference}"
        return Question(
            level        = 1,
            prompt       = prompt,
            operator     = operator,
            target       = reference,
            operands     = operands,
            distractors  = distractors,
            hint         = f"Look for a number that is {op_word} {reference}. "
                           f"{'Bigger numbers are on the right of a number line!' if operator == '>' else 'Smaller numbers are on the left!' if operator == '<' else 'Find the exact same number!'}",
            audio_prompt = f"Touch a number {op_word} {reference}",
        )

    # ------------------------------------------------------------------ #
    #  Level 2 – Single / Double Digit Arithmetic                         #
    # ------------------------------------------------------------------ #

    def level2(self) -> Question:
        cfg = self.config
        use_sub = cfg.allow_subtraction and random.random() < 0.4

        if use_sub:
            # a - b = target,  a > b
            a      = random.randint(5, min(cfg.max_operand, 99))
            b      = random.randint(1, a - 1)
            target = a - b
            operands   = [a, b]
            operator   = '-'
            prompt     = f"Touch {a}, then {b}  ({a} − {b} = ?)"
            audio      = f"Touch {a}, then {b}"
        else:
            # a + b = target
            a      = random.randint(1, min(cfg.max_operand // 2 + 1, 50))
            b      = random.randint(1, min(cfg.max_operand - a, 50))
            target = a + b
            operands   = [a, b]
            operator   = '+'
            prompt = f"Solve: {a} + {b}"
            audio      = f"Solve: {a} + {b}"

        distractors = self._safe_distractors(operands, cfg.distractor_count,
                                              lo=1, hi=max(target + 20, 20))
        return Question(
            level        = 2,
            prompt       = prompt,
            operator     = operator,
            target       = target,
            operands     = operands,
            distractors  = distractors,
            hint         = f"You need to {'add' if operator == '+' else 'subtract'}! "
                           f"Touch {operands[0]} first, then {operands[1]}.",
            audio_prompt = audio,
        )

    # ------------------------------------------------------------------ #
    #  Level 3 – Advanced / Hundreds                                      #
    # ------------------------------------------------------------------ #

    def level3(self) -> Question:
        cfg     = self.config
        multi   = cfg.multi_step

        if multi:
            # 3-operand chain: a OP b OP c = target
            a, b, c = (random.randint(10, max(11, cfg.max_operand // 4)) for _ in range(3))
            ops     = [random.choice(['+', '-']) for _ in range(2)]
            target  = a
            step_strs = [str(a)]
            operands  = [a]
            for op, val in zip(ops, [b, c]):
                if op == '+':
                    target += val
                else:
                    if target - val > 0:
                        target -= val
                    else:
                        target += val
                        op = '+'
                operands.append(val)
                step_strs.append(f"{op} {val}")
            expr     = " ".join(step_strs)
            prompt   = f"Solve: {expr} = ?"
            operator = 'chain'
            audio    = f"Touch {'then'.join(str(x) for x in operands)}"
        else:
            # 2-operand hundreds
            a      = random.randint(10, min(cfg.max_operand, 500))
            b      = random.randint(10, min(cfg.max_operand - a + 10, 500))
            target = a + b
            operands = [a, b]
            operator = '+'
            prompt = f"Solve: {a} + {b}"
            audio      = f"Solve: {a} + {b}"

        distractors = self._safe_distractors(operands, cfg.distractor_count,
                                              lo=1, hi=max(target + 100, 100))
        return Question(
            level        = 3,
            prompt       = prompt,
            operator     = operator,
            target       = target,
            operands     = operands,
            distractors  = distractors,
            hint         = f"Break it into steps! Start with {operands[0]}, "
                           f"then keep going.",
            audio_prompt = audio,
        )

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def generate(self, level: int) -> Question:
        if level == 1:
            return self.level1()
        elif level == 2:
            return self.level2()
        else:
            return self.level3()

    @staticmethod
    def _safe_distractors(correct: List[int], count: int,
                           lo: int, hi: int,
                           exclude_fn=None) -> List[int]:
        pool = set(range(max(1, lo), max(lo + 1, hi)))
        pool -= set(correct)
        if exclude_fn:
            pool = {x for x in pool if not exclude_fn(x)}
        if len(pool) < count:
            # relax constraints
            pool = set(range(max(1, lo), max(lo + 1, hi))) - set(correct)
        sample = random.sample(list(pool), min(count, len(pool)))
        return sample


def _matches_op(x: int, op: str, ref: int) -> bool:
    if op == '>': return x > ref
    if op == '<': return x < ref
    return x == ref
