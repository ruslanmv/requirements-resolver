# Dependency Resolution Algorithms

The Requirements Resolver offers several distinct algorithms to merge and resolve dependencies. Each strategy has unique strengths and is suited for different use cases, from quick checks to building robust, portable applications.

-----

### 1\. Greedy Latest-Compatible

This is the default and fastest approach. For each package, it finds all versions that satisfy the given constraints and simply picks the newest one available.

#### How It Works:

1.  **Aggregate Constraints**: It reads all `requirements.txt` files and combines their version specifiers using a logical **AND**.
      - **Formula**: For a package `P` with specifiers $S\_1, S\_2, \\dots, S\_n$ from different files, the final constraint is the intersection: $S\_{final} = S\_1 \\cap S\_2 \\cap \\dots \\cap S\_n$
2.  **Fetch & Filter**: It queries PyPI for all versions of `P` and filters them, creating a set of compatible versions, `V_compatible`.
3.  **Greedy Choice**: From the filtered list, it selects the absolute latest stable version.
      - **Formula**: $V\_{chosen} = \\max(V\_{compatible})$

#### Workflow:

```
[File 1] -> |                       |
[File 2] -> | Aggregate Constraints | -> [Combined Specifiers] -> [Find Latest Version] -> [Final Version]
...      -> |       (AND)         |
[File N] -> |                       |
```

#### Use Case:

  - **Best for**: Quick checks and simple projects.
  - **Strength**: Very fast. 🚀
  - **Weakness**: Lacks foresight. Choosing the newest version of one package might create a conflict for another.

-----

### 2\. Version Range with Backtracking

This is a more thorough solver that intelligently searches for a combination of versions that works for all packages together.

#### How It Works:

1.  **Collect All Candidates**: It creates a list of *all possible compatible versions* for every package.
2.  **Depth-First Search (DFS)**: It recursively tries to build a valid solution.
      - **Logic**: For a given package $P\_i$, it tries a version $V\_{ij}$. It then recursively calls itself to solve for the next package, $P\_{i+1}$.
3.  **Backtrack on Failure**: If the recursive call for $P\_{i+1}$ fails (returns `False`), it undoes its choice of $V\_{ij}$ and tries the next version, $V\_{i(j+1)}$.

#### Workflow:

```
Start -> P1 (v1.2) -> P2 (v3.4) -> P3 (v5.0) -> [CONFLICT ❌]
             |            |            ^
             |            |            | Backtrack
             |            +-------> P2 (v3.3) -> P3 (v5.1) -> Success ✅
             |
             +-> P1 (v1.1) -> ... (continue search)
```

#### Use Case:

  - **Best for**: Complex projects with many overlapping dependencies where the Greedy algorithm fails.
  - **Strength**: Much more likely to find a valid solution.
  - **Weakness**: Can be significantly slower due to its exhaustive search. 🐢

-----

### 3\. Per-File Isolated Environments

This strategy sidesteps merging by keeping dependencies separate and validating them individually.

#### How It Works:

1.  **Iterate Files**: The algorithm processes one `requirements.txt` file at a time.
2.  **Create Isolated Environment**: For each file, it creates a brand new, completely isolated Python virtual environment (`venv`).
3.  **Install Dependencies**: It runs `pip install -r <file>` inside that dedicated environment.
4.  **Report Outcome**: A failure is reported only if a *single* `requirements.txt` file has internal conflicts.

#### Workflow:

```
             +--> [Create venv_1] --> [pip install -r file1.txt] --> [Result 1]
[File 1] -> /
             
[File 2] -> ----> [Create venv_2] --> [pip install -r file2.txt] --> [Result 2]
             
[File 3] -> \
             +--> [Create venv_3] --> [pip install -r file3.txt] --> [Result 3]
```

#### Use Case:

  - **Best for**: Validating a set of independent tools, each with its own requirements.
  - **Strength**: Guarantees no cross-file conflicts.
  - **Weakness**: Does not produce a single, unified requirements file.

-----

### 4\. Wheelhouse + PEX Bundle

This algorithm creates a single, portable, and self-contained executable file.

#### How It Works:

1.  **Build Wheelhouses**: For each `requirements.txt` file, it runs `pip wheel` to download and build all dependencies into `.whl` files.
2.  **Merge Wheels**: It copies all the `.whl` files from every wheelhouse into a single, merged directory.
3.  **Create PEX File**: It uses the **PEX** (`.pex`) tool to bundle the merged wheels and a Python interpreter into one executable file.

#### Workflow:

```
[File 1] -> [pip wheel] -> |                |
[File 2] -> [pip wheel] -> | Merge All .whl | -> [Merged Wheelhouse] -> [pex build] -> [agentic.pex]
...      -> [pip wheel] -> |   Files        |
[File N] -> [pip wheel] -> |                |
```

#### Use Case:

  - **Best for**: Deploying a Python application to a production environment. 📦
  - **Strength**: Creates a portable, hermetic executable, ideal for deployment.
  - **Weakness**: Requires the `pex` tool to be installed. The final file can be large.

-----

### 5\. Conda-First Hybrid Resolution

This method delegates resolution to the powerful Conda package manager, using its built-in **SAT solver**.

#### How It Works:

1.  **Generate Conda File**: It collects all package specifiers from all files and writes them into a temporary `environment.yml` file.
      - **Logic**: This transforms the dependency problem into a **Boolean Satisfiability Problem (SAT)**, where each package version is a variable, and constraints are clauses.
2.  **Run Conda Solver**: It instructs Conda to solve for the environment specified in the `.yml` file.
3.  **Report Outcome**: If Conda's SAT solver finds a combination of package versions that satisfies all constraints, the resolution succeeds. Otherwise, it fails.

#### Workflow:

```
[File 1] -> |                  |
[File 2] -> | Aggregate All    | -> [environment.yml] -> [Conda SAT Solver] -> [Valid Environment]
...      -> | Requirements     |
[File N] -> |                  |
```

#### Use Case:

  - **Best for**: Projects with complex scientific libraries (NumPy, SciPy, PyTorch) or non-Python dependencies.
  - **Strength**: Extremely powerful and reliable for complex dependency graphs. 🧠
  - **Weakness**: Requires a full Conda installation.