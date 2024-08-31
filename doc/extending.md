# Extending REcover

REcover was designed with modularity in mind, so that users can extend it in
various ways and broaden its capabilities. More specifically, users can:

1. Develop new *exporters* &ndash; MEDIUM

   Exporters are responsible for exporting program data from reverse engineering
   frameworks and storing them in a format recognizable by REcover. For example,
   see [the IDA Pro exporter](https://github.com/huku-/recover/blob/master/src/recover/exporters/ida_pro.py).
   Users are free to implement their own exporters (e.g. for radare, Ghidra,
   Binary Ninja etc.) and run REcover analyses, without worrying about the
   internals of other components. Everything will work as expected as long as:

   * The exported graphs (AFCG, DFG, PDG) obey the definitions given in our paper
     (also see [**graphs.py**](https://github.com/huku-/recover/blob/master/src/recover/graphs/graphs.py)).

   * Information on the program's segments is also exported. See class `Segment`
     in [**exporter.py**](https://github.com/huku-/recover/blob/master/src/recover/exporter.py).

   `Exporter.load_data()` loads the exported information for use by REcover, so
   you can always use it as a guide.

2. Develop new *estimators* &ndash; EASY

   Estimators are given the aforementioned information, exported from a reverse
   engineering framework, and build an initial estimation of the program's
   compile-unit segmentation. **Even though, coming up with a new idea on how to
   construct a sound initial estimation is hard, implementing this idea in
   REcover is relatively simple.** Notice, however, that the more precise the
   initial estimation, the better the optimization results that will eventually
   be produced.

   Estimators are free to perform arbitrary computations, as long as they produce
   a valid compile-unit map a.k.a. [`CUMap`](https://github.com/huku-/recover/blob/master/src/recover/cu_map.py).
   Estimators should inherit from and implement the [`Estimator`](https://github.com/huku-/recover/blob/master/src/recover/estimator.py)
   API.

3. Develop new *fitness functions* &ndash; EASY

   Fitness functions receive an *optimization state* as input and return a real
   value, the fitness score. Notice that the said score should not necessarily
   be in the closed [0, 1] set, but restricting it in that range is generally
   advisable.

   States are represented as bit-vectors, with each bit representing a function
   and set bits representing compile-unit split-points. See our paper and
   [**state.py**](https://github.com/huku-/recover/blob/master/src/recover/state.py)
   for more information.

   Fitness functions should inherit from and implement the [`FitnessFunction`](https://github.com/huku-/recover/blob/master/src/recover/fitness_function.py)
   API. Currently, REcover comes with two fitness functions; one based on the
   Newman Modularity and one based on the Clustering Coefficient, with the former
   outperforming the latter both in terms of speed and precision.

   When implementing custom fitness functions, any CPU- or memory-intensive
   operations should take place in the constructor, as optimizers instantiate a
   single fitness function object and call their `score()` method repeatedly.
   This also allows programmers to keep any required state in their own custom
   class.

4. Developing new *optimizers* &ndash; HARD

   Optimizers take a fitness function and repeatedly generate new optimization
   states and pass them to the latter. Optimization carries on until fitness
   scores cannot be further improved. **Currently, the [`Optimizer`](https://github.com/huku-/recover/blob/master/src/recover/optimizer.py)
   interface implements local optimization of compile-unit pairs, but this might
   change in the future to allow for global optimization.**

   REcover comes with two optimizers; The [brute-force](https://github.com/huku-/recover/blob/master/src/recover/optimizers/brute_force.py)
   optimizer, which explores all possible states and the [genetic](https://github.com/huku-/recover/blob/master/src/recover/optimizers/genetic.py)
   optimizer, based on [PyGAD](https://github.com/ahmedfgad/GeneticAlgorithmPython),
   which explores states based on a simple evolutionary model.

   Unfortunately, implementing global optimization is not for the faint-hearted,
   so we advise users, who would like to extend REcover, to either work on
   developing new local optimization algorithms, new estimators or new fitness
   functions.
