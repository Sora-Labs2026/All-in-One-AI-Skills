# Reinforcement learning: Gymnasium, Stable-Baselines3 and vectorized environments

Read this when an agent must learn a policy by interacting with an environment: control, games, scheduling, resource allocation, robotics in simulation. If historical data already contains the decisions and outcomes and you cannot interact, you need offline RL or contextual bandits, not online RL; if a fixed rule or an optimization solver works, use that.

Physical systems (robots, lab equipment, vehicles, industrial controls): train and validate in simulation first, and get the user's explicit go-ahead before any learned policy acts on real hardware. Add hard safety limits outside the policy.

## Setup and versions

```bash
python -m pip install "stable-baselines3[extra]" gymnasium   # extra: tensorboard, progress bar, Atari wrappers
python -c "import stable_baselines3 as sb3, gymnasium as gym; print(sb3.__version__, gym.__version__)"
```

- Stable-Baselines3 (SB3) 2.x uses Gymnasium, not the old `gym` package. Old-style environments returning 4-tuples need porting.
- Gymnasium 1.0 (2024) changed vector-environment autoreset semantics and some wrapper names. SB3 ships its own `VecEnv` layer, so check which vector API a given piece of code uses before mixing them.
- Extras: `sb3-contrib` (RecurrentPPO, MaskablePPO, TQC, QR-DQN), RL Zoo (tuned hyperparameters and training scripts), SBX (JAX implementations, faster on some workloads).

## The environment contract

```python
import gymnasium as gym
import numpy as np
from gymnasium import spaces

class InventoryEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, max_steps: int = 200):
        super().__init__()
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(4,), dtype=np.float32)
        self.action_space = spaces.Discrete(5)
        self.max_steps = max_steps

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)                      # seeds self.np_random
        self.t = 0
        self.state = self.np_random.uniform(0.2, 0.8, size=4).astype(np.float32)
        return self.state.copy(), {}

    def step(self, action):
        self.t += 1
        # ... update self.state from action using self.np_random for any randomness ...
        reward = float(-np.abs(self.state[0] - 0.5))
        terminated = bool(self.state[0] <= 0.0)       # a true terminal state of the task
        truncated = self.t >= self.max_steps          # a time limit, not a failure
        return self.state.copy(), reward, terminated, truncated, {}
```

- **terminated versus truncated** matters: on truncation the value of the next state is still bootstrapped; on termination it is zero. Reporting a time limit as `terminated` biases value estimates.
- Use `self.np_random` for all randomness so seeding works.
- Observations must match `observation_space` exactly (dtype and shape). Normalize to roughly unit scale or use `VecNormalize`.
- Validate with `from stable_baselines3.common.env_checker import check_env; check_env(InventoryEnv())`.
- Wrap with `Monitor` (or use `make_vec_env`, which does) so episode returns and lengths are recorded.

## Pick the algorithm

| Action space and constraints | Start with | Notes |
|---|---|---|
| Discrete, cheap simulator | PPO | Robust default; many parallel environments |
| Discrete, expensive simulator | DQN (or QR-DQN) | Off-policy, replay buffer reuses samples |
| Continuous control | SAC | Sample-efficient, stable; TD3 as an alternative |
| Continuous, cheap simulator, many workers | PPO | Simple, scales with parallel environments |
| Goal-conditioned with sparse reward | SAC or DQN with hindsight experience replay (HER) | Needs a goal-based observation dictionary |
| Partial observability | RecurrentPPO (sb3-contrib) or stacked frames | Try frame stacking first |
| Invalid actions in some states | MaskablePPO (sb3-contrib) | Better than penalizing invalid actions |

Take starting hyperparameters from RL Zoo for similar environments rather than library defaults.

## Vectorized environments

```python
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize

venv = make_vec_env(InventoryEnv, n_envs=8, seed=0, vec_env_cls=SubprocVecEnv)
venv = VecNormalize(venv, norm_obs=True, norm_reward=True, clip_obs=10.0)
model = PPO("MlpPolicy", venv, n_steps=1024, batch_size=256, learning_rate=3e-4, seed=0,
            verbose=1, tensorboard_log="runs")
model.learn(total_timesteps=1_000_000)
model.save("ppo_inventory"); venv.save("vecnormalize.pkl")     # save the statistics too
```

- `DummyVecEnv` runs environments sequentially in one process: best for fast, light environments (the process overhead of subprocesses outweighs the gain). `SubprocVecEnv` runs each in its own process: for slow, CPU-heavy simulators. Measure steps per second both ways.
- SB3 vector environments auto-reset; the last observation of a finished episode is in `infos[i]["terminal_observation"]`, and `step` returns 4 values `(obs, rewards, dones, infos)`.
- For on-policy algorithms, more environments shorten wall-clock time; keep `n_steps x n_envs` (the rollout size) sensible relative to `batch_size`.
- For off-policy algorithms with several environments, consider `gradient_steps=-1` to do one gradient step per environment step collected.
- Very high throughput: C++ or JAX environments (EnvPool, Brax, Gymnax) or a high-throughput RL library (PufferLib and similar) can reach millions of steps per second. Their APIs differ from SB3; check versions and keep evaluation identical when you switch.
- Multi-agent environments use the PettingZoo API; SB3 is single-agent, so use parameter sharing through wrappers or a multi-agent library.

## Evaluation that means something

```python
from stable_baselines3.common.callbacks import EvalCallback
from stable_baselines3.common.evaluation import evaluate_policy

eval_env = VecNormalize(make_vec_env(InventoryEnv, n_envs=1, seed=1000), training=False, norm_reward=False)
eval_cb = EvalCallback(eval_env, eval_freq=10_000, n_eval_episodes=20, deterministic=True,
                       best_model_save_path="best")
# later, for a final score: load the saved normalization statistics into a fresh eval env
eval_env = VecNormalize.load("vecnormalize.pkl", make_vec_env(InventoryEnv, n_envs=1, seed=2000))
eval_env.training, eval_env.norm_reward = False, False
mean_r, std_r = evaluate_policy(PPO.load("ppo_inventory"), eval_env, n_eval_episodes=100, deterministic=True)
```

- Evaluate on a **separate environment instance with different seeds** from training. When the task has variations (layouts, demand patterns, levels), hold some out entirely to test generalization.
- With `VecNormalize`, evaluation must use the training statistics with `training=False` and `norm_reward=False`; otherwise statistics drift during evaluation and returns are reported in normalized units.
- Train **at least 5 seeds** (10 for publication-grade claims) and report the mean with a confidence interval, or the interquartile mean with bootstrap intervals. RL results vary widely between seeds; a single curve is not evidence.
- Compare against baselines: random policy, a hand-written heuristic, and the current production rule. An agent that cannot beat a simple heuristic is not ready.
- Report environment steps, not only wall-clock time, so sample efficiency is comparable.

## Reward design

- Reward exactly what you want, measured in the task's units, and nothing else. Shaped rewards (bonuses for intermediate progress) speed learning but can be exploited; potential-based shaping preserves optimal policies.
- Watch for reward hacking: inspect episodes of the best policy by eye or with logs, not only the return curve.
- Scale rewards to roughly unit magnitude per step (or use `VecNormalize(norm_reward=True)` during training).

## Debugging order

1. `check_env`, then step the environment by hand with random actions and print observations, rewards and done flags.
2. Train on a trivially easy version (short horizon, dense reward). If PPO cannot learn it, suspect the environment.
3. Watch entropy, explained variance (PPO), Q-values (DQN, SAC) and episode length in TensorBoard alongside returns.
4. Learning collapses after progress: lower the learning rate, check for value explosion, clip rewards or gradients.
5. Nothing learns: check observation scaling, action-space bounds (continuous actions should be in [-1, 1] with rescaling inside the environment), and whether the reward is too sparse.

## Persistence

- `model.save` stores policy and optimizer state but not the replay buffer (save it separately with `save_replay_buffer` for off-policy resumption) and not `VecNormalize` statistics.
- Loading SB3 zip files uses pickle for some parts: load only files you trust.
- Record the SB3, Gymnasium and environment versions with the model; environment code changes invalidate comparisons.

## Pitfalls

| Pitfall | Fix |
|---|---|
| Time limits reported as `terminated` | `truncated=True` for time limits |
| Evaluating on the training environment instance and seeds | Separate eval environment and seeds; held-out task variations |
| `VecNormalize` statistics not saved or updated during evaluation | Save them; `training=False`, `norm_reward=False` at evaluation |
| One seed, one curve | 5+ seeds with intervals |
| `SubprocVecEnv` for a trivial environment | `DummyVecEnv`; measure steps per second |
| Continuous actions far outside [-1, 1] | Normalize the action space and rescale inside the environment |
| Policy deployed to hardware straight from training | Simulation validation, safety limits, explicit user approval |

## Done when

- [ ] The environment passes `check_env`, separates terminated from truncated, and seeds all randomness.
- [ ] Results cover 5+ seeds on separate evaluation environments, with intervals and steps reported.
- [ ] The policy beats random and heuristic baselines, and its episodes were inspected for reward hacking.
- [ ] Model, normalization statistics and versions are saved together.
- [ ] Nothing ran on physical hardware without simulation validation and the user's explicit approval.
