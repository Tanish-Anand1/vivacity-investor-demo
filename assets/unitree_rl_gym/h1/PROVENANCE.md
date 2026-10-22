# Unitree H1 matched model and walking policy

Source: [`unitreerobotics/unitree_rl_gym`](https://github.com/unitreerobotics/unitree_rl_gym)
at commit `276801e46c5d433564f24658bac64f254b7d2d4b` (BSD-3-Clause;
see `LICENSE`). The `h1.xml`, `scene.xml`, `assets/*.STL`,
`policy/motion.pt`, `policy/h1.yaml`, and `policy/deploy_mujoco_reference.py`
files are copied from that commit. `assets/` is the vendor `meshes/` directory
under a path recognized by Vivacity's MuJoCo loader; mesh bytes are unchanged.

The TorchScript checkpoint SHA-256 is
`44a0fbceb81f3877833ae9a398d039bea1759cb0d3c8188181013885f70589eb`.
`scripts/convert_h1_policy.py` exports its tensors into `policy/motion.npz`
and tests 256 sequential recurrent outputs against TorchScript. The runtime
loads only the NumPy weights and creates isolated recurrent state per trial.

The Vivacity scene adds a ground plane, a bounded low threshold, a visual goal,
and a standing keyframe. These are adaptations and are not claimed as vendor
training conditions or as hardware validation.
