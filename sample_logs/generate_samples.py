"""
sample_logs フォルダ配下に最小構成および推奨構成（標準RL、SAP-net、継続学習）の
サンプル実験ログデータを自動生成するスクリプト。
"""
import os
import json
import yaml
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def create_plot(filepath: str, title: str, xlabel: str, ylabel: str, x_data, y_data, label: str = "Series"):
    plt.figure(figsize=(7, 4), dpi=100)
    plt.plot(x_data, y_data, label=label, color="#2563eb", linewidth=1.5)
    plt.title(title, fontsize=12)
    plt.xlabel(xlabel, fontsize=10)
    plt.ylabel(ylabel, fontsize=10)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filepath)
    plt.close()


def create_trajectory_plot(filepath: str, title: str, start=(0, 0), goal=(10, 5), points=None):
    plt.figure(figsize=(6, 5), dpi=100)
    if points is not None:
        xs, ys = zip(*points)
        plt.plot(xs, ys, color="#10b981", linewidth=2, label="Trajectory")
    plt.scatter([start[0]], [start[1]], color="#3b82f6", s=100, marker="o", label="Start")
    plt.scatter([goal[0]], [goal[1]], color="#ef4444", s=120, marker="*", label="Goal")
    plt.title(title, fontsize=12)
    plt.xlabel("X [m]", fontsize=10)
    plt.ylabel("Y [m]", fontsize=10)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(filepath)
    plt.close()


def generate_minimal_generic_rl():
    target_dir = os.path.join(BASE_DIR, "1_minimal_generic_rl")
    os.makedirs(target_dir, exist_ok=True)

    # 1. exp_cartpole_dqn
    dir_dqn = os.path.join(target_dir, "exp_cartpole_dqn")
    os.makedirs(dir_dqn, exist_ok=True)
    
    np.random.seed(42)
    steps = np.arange(10, 1010, 10)
    reward = np.minimum(200.0, 15.0 + 0.18 * steps + np.random.normal(0, 10, len(steps)))
    loss = np.maximum(0.01, 1.5 * np.exp(-steps / 300.0) + np.random.normal(0, 0.05, len(steps)))
    q_value = 5.0 + 0.05 * steps + np.random.normal(0, 1, len(steps))
    epsilon = np.maximum(0.01, 1.0 - (steps / 800.0))

    df_dqn = pd.DataFrame({
        "step": steps,
        "reward": np.round(reward, 2),
        "loss": np.round(loss, 4),
        "q_value": np.round(q_value, 2),
        "epsilon": np.round(epsilon, 3)
    })
    df_dqn.to_csv(os.path.join(dir_dqn, "progress.csv"), index=False)

    config_dqn = {
        "algorithm": "DQN",
        "environment": "CartPole-v1",
        "hyperparameters": {
            "learning_rate": 0.001,
            "gamma": 0.99,
            "batch_size": 64,
            "buffer_size": 20000,
            "target_update_interval": 200
        }
    }
    with open(os.path.join(dir_dqn, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config_dqn, f, indent=2, ensure_ascii=False)

    create_plot(os.path.join(dir_dqn, "eval_curve.png"), "DQN CartPole Reward", "Step", "Reward", steps, reward)

    # 2. exp_cartpole_ppo
    dir_ppo = os.path.join(target_dir, "exp_cartpole_ppo")
    os.makedirs(dir_ppo, exist_ok=True)

    np.random.seed(99)
    steps_ppo = np.arange(10, 1010, 10)
    reward_ppo = np.minimum(200.0, 25.0 + 0.22 * steps_ppo + np.random.normal(0, 8, len(steps_ppo)))
    actor_loss = np.random.normal(0.05, 0.02, len(steps_ppo))
    critic_loss = np.maximum(0.005, 1.0 * np.exp(-steps_ppo / 250.0) + np.random.normal(0, 0.03, len(steps_ppo)))
    entropy = np.maximum(0.1, 0.69 - 0.0005 * steps_ppo + np.random.normal(0, 0.02, len(steps_ppo)))

    df_ppo = pd.DataFrame({
        "step": steps_ppo,
        "reward": np.round(reward_ppo, 2),
        "actor_loss": np.round(actor_loss, 4),
        "critic_loss": np.round(critic_loss, 4),
        "entropy": np.round(entropy, 4)
    })
    df_ppo.to_csv(os.path.join(dir_ppo, "progress.csv"), index=False)

    config_ppo = {
        "algorithm": "PPO",
        "environment": "CartPole-v1",
        "hyperparameters": {
            "learning_rate": 0.0003,
            "gamma": 0.99,
            "clip_range": 0.2,
            "n_steps": 2048,
            "entropy_coef": 0.01
        }
    }
    with open(os.path.join(dir_ppo, "params.json"), "w", encoding="utf-8") as f:
        json.dump(config_ppo, f, indent=2, ensure_ascii=False)

    create_plot(os.path.join(dir_ppo, "eval_curve.png"), "PPO CartPole Reward", "Step", "Reward", steps_ppo, reward_ppo)


def generate_recommended_standard_rl():
    target_dir = os.path.join(BASE_DIR, "2_recommended_standard_rl")
    os.makedirs(target_dir, exist_ok=True)

    # 1. output_20260901_100000 (Baseline Q-Learning)
    ts1 = "20260901_100000"
    dir1 = os.path.join(target_dir, f"output_{ts1}")
    os.makedirs(dir1, exist_ok=True)

    n_episodes = 80
    np.random.seed(123)
    episodes = np.arange(1, n_episodes + 1)
    
    goal_prob = 1.0 / (1.0 + np.exp(-(episodes - 35) / 10.0))
    results = [ "Goal" if np.random.rand() < p else "Collision" for p in goal_prob ]
    steps = [ int(np.random.normal(50, 8)) if r == "Goal" else int(np.random.normal(30, 10)) for r in results ]
    steps = [ max(5, s) for s in steps ]
    rewards = [ round(100.0 - 0.5 * s + np.random.normal(0, 5), 2) if r == "Goal" else round(-50.0 - 0.2 * s + np.random.normal(0, 5), 2) for s, r in zip(steps, results) ]
    
    final_x = [ round(11.0 + np.random.normal(0, 0.2), 2) if r == "Goal" else round(np.random.uniform(2, 9), 2) for r in results ]
    final_y = [ round(3.0 + np.random.normal(0, 0.2), 2) if r == "Goal" else round(np.random.uniform(1, 4), 2) for r in results ]

    df1 = pd.DataFrame({
        "Episode": episodes,
        "Steps": steps,
        "TotalReward": rewards,
        "Result": results,
        "Final_X": final_x,
        "Final_Y": final_y,
        "UnsafeActions": [0] * n_episodes,
        "SAP_Plan": ["None"] * n_episodes
    })
    df1.to_csv(os.path.join(dir1, f"learning_log_{ts1}.csv"), index=False)

    config1 = {
        "experiment_name": "Standard_RL_Q_Learning_Baseline",
        "algorithm": "Q-Learning",
        "learning": {
            "alpha": 0.1,
            "gamma": 0.95,
            "epsilon_initial": 1.0,
            "epsilon_decay": 0.98,
            "epsilon_min": 0.05
        },
        "target_goal": {"x": 11.0, "y": 3.0}
    }
    with open(os.path.join(dir1, f"config_used_{ts1}.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(config1, f, allow_unicode=True, sort_keys=False)

    create_plot(os.path.join(dir1, f"learning_rewards_{ts1}.png"), "Episode Rewards (Baseline)", "Episode", "Total Reward", episodes, rewards)
    create_plot(os.path.join(dir1, f"learning_steps_{ts1}.png"), "Episode Steps (Baseline)", "Episode", "Steps", episodes, steps)
    
    t_points = [(0, 0), (2, 1), (4, 1.5), (6, 2.2), (8, 2.5), (10, 2.8), (11, 3.0)]
    create_trajectory_plot(os.path.join(dir1, f"trajectory_{ts1}.png"), "Final Trajectory (Baseline)", goal=(11, 3), points=t_points)

    # 2. output_20260901_120000 (Tuned Q-Learning)
    ts2 = "20260901_120000"
    dir2 = os.path.join(target_dir, f"output_{ts2}")
    os.makedirs(dir2, exist_ok=True)

    np.random.seed(456)
    goal_prob2 = 1.0 / (1.0 + np.exp(-(episodes - 22) / 8.0))
    results2 = [ "Goal" if np.random.rand() < p else "Collision" for p in goal_prob2 ]
    steps2 = [ int(np.random.normal(42, 6)) if r == "Goal" else int(np.random.normal(25, 8)) for r in results2 ]
    steps2 = [ max(5, s) for s in steps2 ]
    rewards2 = [ round(110.0 - 0.4 * s + np.random.normal(0, 4), 2) if r == "Goal" else round(-40.0 - 0.2 * s + np.random.normal(0, 4), 2) for s, r in zip(steps2, results2) ]
    
    final_x2 = [ round(11.0 + np.random.normal(0, 0.15), 2) if r == "Goal" else round(np.random.uniform(2, 9), 2) for r in results2 ]
    final_y2 = [ round(3.0 + np.random.normal(0, 0.15), 2) if r == "Goal" else round(np.random.uniform(1, 4), 2) for r in results2 ]

    df2 = pd.DataFrame({
        "Episode": episodes,
        "Steps": steps2,
        "TotalReward": rewards2,
        "Result": results2,
        "Final_X": final_x2,
        "Final_Y": final_y2,
        "UnsafeActions": [0] * n_episodes,
        "SAP_Plan": ["None"] * n_episodes
    })
    df2.to_csv(os.path.join(dir2, f"learning_log_{ts2}.csv"), index=False)

    config2 = {
        "experiment_name": "Standard_RL_Q_Learning_Tuned",
        "algorithm": "Q-Learning",
        "learning": {
            "alpha": 0.05,
            "gamma": 0.99,
            "epsilon_initial": 1.0,
            "epsilon_decay": 0.95,
            "epsilon_min": 0.01
        },
        "target_goal": {"x": 11.0, "y": 3.0}
    }
    with open(os.path.join(dir2, f"config_used_{ts2}.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(config2, f, allow_unicode=True, sort_keys=False)

    create_plot(os.path.join(dir2, f"learning_rewards_{ts2}.png"), "Episode Rewards (Tuned)", "Episode", "Total Reward", episodes, rewards2)
    create_plot(os.path.join(dir2, f"learning_steps_{ts2}.png"), "Episode Steps (Tuned)", "Episode", "Steps", episodes, steps2)
    
    t_points2 = [(0, 0), (2, 0.8), (4, 1.8), (6, 2.0), (8, 2.6), (10, 2.9), (11, 3.0)]
    create_trajectory_plot(os.path.join(dir2, f"trajectory_{ts2}.png"), "Final Trajectory (Tuned)", goal=(11, 3), points=t_points2)


def generate_recommended_sap_net():
    target_dir = os.path.join(BASE_DIR, "3_recommended_sap_net")
    os.makedirs(target_dir, exist_ok=True)

    n_episodes = 80
    episodes = np.arange(1, n_episodes + 1)

    # 1. output_20260905_140000 (SAP-net lambda=0.5)
    ts1 = "20260905_140000"
    dir1 = os.path.join(target_dir, f"output_{ts1}")
    os.makedirs(dir1, exist_ok=True)

    np.random.seed(777)
    goal_prob = 1.0 / (1.0 + np.exp(-(episodes - 18) / 6.0))
    results = [ "Goal" if np.random.rand() < p else "Collision" for p in goal_prob ]
    steps = [ int(np.random.normal(48, 5)) if r == "Goal" else int(np.random.normal(35, 8)) for r in results ]
    rewards = [ round(95.0 - 0.4 * s + np.random.normal(0, 4), 2) if r == "Goal" else round(-30.0 - 0.1 * s + np.random.normal(0, 3), 2) for s, r in zip(steps, results) ]
    unsafe = [ int(max(0, np.random.normal(4 * np.exp(-e / 20.0), 0.8))) for e in episodes ]
    sap_plans = [ f"Plan_A_{e%3}" if u > 0 else "None" for e, u in zip(episodes, unsafe) ]

    df1 = pd.DataFrame({
        "Episode": episodes,
        "Steps": steps,
        "TotalReward": rewards,
        "Result": results,
        "Final_X": [ 11.0 if r == "Goal" else 8.5 for r in results ],
        "Final_Y": [ 3.0 if r == "Goal" else 2.1 for r in results ],
        "UnsafeActions": unsafe,
        "SAP_Plan": sap_plans
    })
    df1.to_csv(os.path.join(dir1, f"learning_log_{ts1}.csv"), index=False)

    config1 = {
        "experiment_name": "SAP_net_Safety_Weight_0_5",
        "algorithm": "SAP-net",
        "safety": {
            "safety_weight_lambda": 0.5,
            "danger_threshold": 0.4,
            "enable_online_intervention": True
        },
        "target_goal": {"x": 11.0, "y": 3.0}
    }
    with open(os.path.join(dir1, f"config_used_{ts1}.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(config1, f, allow_unicode=True, sort_keys=False)

    create_plot(os.path.join(dir1, f"learning_rewards_{ts1}.png"), "SAP-net (λ=0.5) Rewards", "Episode", "Total Reward", episodes, rewards)
    create_plot(os.path.join(dir1, f"learning_steps_{ts1}.png"), "SAP-net (λ=0.5) Steps", "Episode", "Steps", episodes, steps)
    t_points1 = [(0, 0), (2, 1.2), (4, 2.0), (6, 2.5), (8, 2.7), (10, 2.9), (11, 3.0)]
    create_trajectory_plot(os.path.join(dir1, f"trajectory_{ts1}.png"), "SAP-net Trajectory (λ=0.5)", goal=(11, 3), points=t_points1)

    # 2. output_20260905_160000 (SAP-net lambda=0.8)
    ts2 = "20260905_160000"
    dir2 = os.path.join(target_dir, f"output_{ts2}")
    os.makedirs(dir2, exist_ok=True)

    np.random.seed(888)
    goal_prob2 = 1.0 / (1.0 + np.exp(-(episodes - 14) / 5.0))
    results2 = [ "Goal" if np.random.rand() < p else "Collision" for p in goal_prob2 ]
    steps2 = [ int(np.random.normal(52, 4)) if r == "Goal" else int(np.random.normal(30, 6)) for r in results2 ]
    rewards2 = [ round(90.0 - 0.35 * s + np.random.normal(0, 3), 2) if r == "Goal" else round(-25.0 - 0.1 * s + np.random.normal(0, 3), 2) for s, r in zip(steps2, results2) ]
    unsafe2 = [ int(max(0, np.random.normal(2.5 * np.exp(-e / 15.0), 0.5))) for e in episodes ]
    sap_plans2 = [ f"Plan_B_{e%2}" if u > 0 else "None" for e, u in zip(episodes, unsafe2) ]

    df2 = pd.DataFrame({
        "Episode": episodes,
        "Steps": steps2,
        "TotalReward": rewards2,
        "Result": results2,
        "Final_X": [ 11.0 if r == "Goal" else 9.0 for r in results2 ],
        "Final_Y": [ 3.0 if r == "Goal" else 2.5 for r in results2 ],
        "UnsafeActions": unsafe2,
        "SAP_Plan": sap_plans2
    })
    df2.to_csv(os.path.join(dir2, f"learning_log_{ts2}.csv"), index=False)

    config2 = {
        "experiment_name": "SAP_net_Safety_Weight_0_8",
        "algorithm": "SAP-net",
        "safety": {
            "safety_weight_lambda": 0.8,
            "danger_threshold": 0.3,
            "enable_online_intervention": True
        },
        "target_goal": {"x": 11.0, "y": 3.0}
    }
    with open(os.path.join(dir2, f"config_used_{ts2}.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(config2, f, allow_unicode=True, sort_keys=False)

    create_plot(os.path.join(dir2, f"learning_rewards_{ts2}.png"), "SAP-net (λ=0.8) Rewards", "Episode", "Total Reward", episodes, rewards2)
    create_plot(os.path.join(dir2, f"learning_steps_{ts2}.png"), "SAP-net (λ=0.8) Steps", "Episode", "Steps", episodes, steps2)
    t_points2 = [(0, 0), (1.8, 1.5), (3.8, 2.3), (6.2, 2.7), (8.5, 2.8), (10.2, 2.9), (11, 3.0)]
    create_trajectory_plot(os.path.join(dir2, f"trajectory_{ts2}.png"), "SAP-net Trajectory (λ=0.8)", goal=(11, 3), points=t_points2)


def generate_recommended_continual_learning():
    target_dir = os.path.join(BASE_DIR, "4_recommended_continual_learning")
    os.makedirs(target_dir, exist_ok=True)

    tasks_info = [
        {"id": 1, "episodes": 30, "goal": (11.0, 3.0), "conv_at": 25},
        {"id": 2, "episodes": 30, "goal": (15.0, 5.0), "conv_at": 22},
        {"id": 3, "episodes": 30, "goal": (8.0, 6.0), "conv_at": 20},
    ]

    def build_continual_df(seed_val, fast_learning=False):
        np.random.seed(seed_val)
        rows = []
        tot_ep = 1
        acquired_policies = 0

        for t in tasks_info:
            t_id = t["id"]
            n_ep = t["episodes"]
            conv_at = t["conv_at"] - (5 if fast_learning else 0)
            gx, gy = t["goal"]

            for ep in range(1, n_ep + 1):
                is_conv = (ep == conv_at)
                if is_conv:
                    acquired_policies += 1
                
                p_goal = 1.0 / (1.0 + np.exp(-(ep - (conv_at - 8)) / 4.0))
                res = "Goal" if np.random.rand() < p_goal else "Collision"
                steps = int(np.random.normal(45, 5)) if res == "Goal" else int(np.random.normal(25, 8))
                steps = max(5, steps)
                rew = round(100.0 - 0.4 * steps + np.random.normal(0, 4), 2) if res == "Goal" else round(-40.0 + np.random.normal(0, 5), 2)
                
                fx = round(gx + np.random.normal(0, 0.2), 2) if res == "Goal" else round(gx - np.random.uniform(2, 5), 2)
                fy = round(gy + np.random.normal(0, 0.2), 2) if res == "Goal" else round(gy - np.random.uniform(1, 3), 2)
                
                unsafe = int(max(0, np.random.normal(3 * np.exp(-ep / 10.0), 0.5)))
                sap_plan = f"Plan_T{t_id}" if unsafe > 0 else ""

                rows.append({
                    "Task_ID": t_id,
                    "Task_Episode": ep,
                    "Total_Episode": tot_ep,
                    "Goal_X": gx,
                    "Goal_Y": gy,
                    "Steps": steps,
                    "TotalReward": rew,
                    "Result": res,
                    "Final_X": fx,
                    "Final_Y": fy,
                    "Is_Converged": is_conv,
                    "Acquired_Policies": acquired_policies,
                    "UnsafeActions": unsafe,
                    "SAP_Plan": sap_plan
                })
                tot_ep += 1
        return pd.DataFrame(rows)

    # 1. output_20260920_100000 (Continual Learning Baseline)
    ts1 = "20260920_100000"
    dir1 = os.path.join(target_dir, f"output_{ts1}")
    os.makedirs(dir1, exist_ok=True)

    df1 = build_continual_df(seed_val=101, fast_learning=False)
    df1.to_csv(os.path.join(dir1, f"learning_log_{ts1}.csv"), index=False)

    config1 = {
        "experiment_name": "S_SAP_Continual_Learning_Baseline",
        "algorithm": "S-SAP",
        "continual_learning": {
            "mode": "sequential_tasks",
            "knowledge_transfer": True,
            "policy_library_path": f"./acquired_policies_{ts1}"
        },
        "tasks": [
            {"task_id": 1, "goal": [11.0, 3.0]},
            {"task_id": 2, "goal": [15.0, 5.0]},
            {"task_id": 3, "goal": [8.0, 6.0]}
        ]
    }
    with open(os.path.join(dir1, f"config_used_{ts1}.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(config1, f, allow_unicode=True, sort_keys=False)

    create_plot(os.path.join(dir1, f"continual_learning_curve_{ts1}.png"), "Continual Learning Curve (All Tasks)", "Total Episode", "Reward", df1["Total_Episode"], df1["TotalReward"])
    
    for t_id in [1, 2, 3]:
        df_t = df1[df1["Task_ID"] == t_id]
        create_plot(os.path.join(dir1, f"learning_rewards_{ts1}_task_{t_id}.png"), f"Task {t_id} Rewards", "Episode", "Reward", df_t["Task_Episode"], df_t["TotalReward"])
        create_plot(os.path.join(dir1, f"learning_steps_{ts1}_task_{t_id}.png"), f"Task {t_id} Steps", "Episode", "Steps", df_t["Task_Episode"], df_t["Steps"])
    
    t_points1 = [(0, 0), (2, 1), (4, 2), (6, 3), (8, 4), (10, 5), (12, 5.2), (15, 5)]
    create_trajectory_plot(os.path.join(dir1, f"trajectory_{ts1}.png"), "Final Trajectory (Task 2)", goal=(15, 5), points=t_points1)

    # 2. output_20260920_150000 (Continual Learning Fast Adaptation)
    ts2 = "20260920_150000"
    dir2 = os.path.join(target_dir, f"output_{ts2}")
    os.makedirs(dir2, exist_ok=True)

    df2 = build_continual_df(seed_val=202, fast_learning=True)
    df2.to_csv(os.path.join(dir2, f"learning_log_{ts2}.csv"), index=False)

    config2 = {
        "experiment_name": "S_SAP_Continual_Learning_Fast_Adapt",
        "algorithm": "S-SAP",
        "continual_learning": {
            "mode": "sequential_tasks",
            "knowledge_transfer": True,
            "fast_transfer_boost": True,
            "policy_library_path": f"./acquired_policies_{ts2}"
        },
        "tasks": [
            {"task_id": 1, "goal": [11.0, 3.0]},
            {"task_id": 2, "goal": [15.0, 5.0]},
            {"task_id": 3, "goal": [8.0, 6.0]}
        ]
    }
    with open(os.path.join(dir2, f"config_used_{ts2}.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(config2, f, allow_unicode=True, sort_keys=False)

    create_plot(os.path.join(dir2, f"continual_learning_curve_{ts2}.png"), "Continual Learning Curve (Fast Adapt)", "Total Episode", "Reward", df2["Total_Episode"], df2["TotalReward"])
    for t_id in [1, 2, 3]:
        df_t = df2[df2["Task_ID"] == t_id]
        create_plot(os.path.join(dir2, f"learning_rewards_{ts2}_task_{t_id}.png"), f"Task {t_id} Rewards (Fast)", "Episode", "Reward", df_t["Task_Episode"], df_t["TotalReward"])
        create_plot(os.path.join(dir2, f"learning_steps_{ts2}_task_{t_id}.png"), f"Task {t_id} Steps (Fast)", "Episode", "Steps", df_t["Task_Episode"], df_t["Steps"])

    t_points2 = [(0, 0), (2, 1.2), (4, 2.5), (6, 3.5), (8, 4.2), (11, 4.8), (13, 5.0), (15, 5)]
    create_trajectory_plot(os.path.join(dir2, f"trajectory_{ts2}.png"), "Final Trajectory (Task 2 Fast)", goal=(15, 5), points=t_points2)


def main():
    print("Generating Minimal Generic RL samples...")
    generate_minimal_generic_rl()
    print("Generating Recommended Standard RL samples...")
    generate_recommended_standard_rl()
    print("Generating Recommended SAP-net samples...")
    generate_recommended_sap_net()
    print("Generating Recommended Continual Learning samples...")
    generate_recommended_continual_learning()
    print("All sample logs generated successfully!")


if __name__ == "__main__":
    main()
