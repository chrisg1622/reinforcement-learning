import matplotlib.pyplot as plt
import pyvirtualdisplay

import tensorflow as tf
from tf_agents.agents.dqn import dqn_agent
from tf_agents.environments import suite_gym
from tf_agents.environments import tf_py_environment
from tf_agents.metrics import tf_metrics
from tf_agents.networks import q_network
from tf_agents.policies import random_tf_policy
from tf_agents.replay_buffers import tf_uniform_replay_buffer
from tf_agents.utils import common

from core.utils import compute_avg_return
from core.utils import collect_data
from core.utils import create_policy_eval_video


display = pyvirtualdisplay.Display(visible=0, size=(1400, 900)).start()


num_iterations = 20000

initial_collect_steps = 1000
collect_steps_per_iteration = 1
replay_buffer_max_length = 100000

batch_size = 64
learning_rate = 1e-3
log_interval = 200

num_eval_episodes = 10
eval_interval = 1000


env_name = 'CartPole-v0'
train_py_env = suite_gym.load(env_name)
eval_py_env = suite_gym.load(env_name)
train_env = tf_py_environment.TFPyEnvironment(train_py_env)
eval_env = tf_py_environment.TFPyEnvironment(eval_py_env)

q_network = q_network.QNetwork(
    input_tensor_spec=train_env.observation_spec(),
    action_spec=train_env.action_spec(),
    fc_layer_params=(100,)
)

agent = dqn_agent.DqnAgent(
    time_step_spec=train_env.time_step_spec(),
    action_spec=train_env.action_spec(),
    q_network=q_network,
    optimizer=tf.compat.v1.train.AdamOptimizer(learning_rate=learning_rate),
    td_errors_loss_fn=common.element_wise_squared_loss,
    train_step_counter=tf.Variable(0)
)
agent.initialize()

random_policy = random_tf_policy.RandomTFPolicy(
    time_step_spec=train_env.time_step_spec(),
    action_spec=train_env.action_spec()
)

average_return = tf_metrics.AverageReturnMetric()


replay_buffer = tf_uniform_replay_buffer.TFUniformReplayBuffer(
    data_spec=agent.collect_data_spec,
    batch_size=train_env.batch_size,
    max_length=replay_buffer_max_length
)


collect_data(train_env, random_policy, replay_buffer, steps=100)

dataset = replay_buffer.as_dataset(
    num_parallel_calls=3,
    sample_batch_size=batch_size,
    single_deterministic_pass=False,
    num_steps=2
).prefetch(3)

iterator = iter(dataset)

# (Optional) Optimize by wrapping some of the code in a graph using TF function.
agent.train = common.function(agent.train)

# Reset the train step
agent.train_step_counter.assign(0)

# Evaluate the agent's policy once before training.
avg_return = compute_avg_return(eval_env, agent.policy, num_eval_episodes)
returns = [avg_return]

for _ in range(num_iterations):
    # Collect a few steps using collect_policy and save to the replay buffer
    collect_data(environment=train_env, policy=agent.collect_policy, buffer=replay_buffer, steps=collect_steps_per_iteration)

    # Sample a batch of data from the buffer and update the agent's network.
    experience, unused_info = next(iterator)
    train_loss = agent.train(experience).loss

    step = agent.train_step_counter.numpy()
    if step % log_interval == 0:
        print(f'step = {step}: loss = {train_loss}')
    if step % eval_interval == 0:
        avg_return = compute_avg_return(eval_env, agent.policy, num_eval_episodes)
        print(f'step = {step}: Average Return = {avg_return}')
        returns.append(avg_return)

iterations = range(0, num_iterations + 1, eval_interval)
plt.plot(iterations, returns)
plt.ylabel('Average Return')
plt.xlabel('Iterations')
plt.ylim(top=250)
plt.savefig(fname='data/trained-agent.png')

create_policy_eval_video(eval_env, eval_py_env, agent.policy, "data/trained-agent")

