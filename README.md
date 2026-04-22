# SIMPL: Super Interesting Minimalist Programming Language
## Intro
Sometimes, there are things we as programmers dislike about the languages we use. In C, for example, there's the pointer and the `*` and `&` symbols. In Rust, the compiler is helpful yet notoriously strict. Python is too high-level and too slow. All of these languages have something in common, though: they are too complicated. What if there were something ... SIMPLer?

That's where **SIMPL: Super Interesting Minimalist Programming Language** comes in. (Before I say too much more, I did some research to see if, in fact, the acronym "SIMPL" or the name "Super Interesting Minimalist Programming Language" already exist, and to my surprise, they do not.) Like the infamous BF programming language, SIMPL only uses a small set of symbols, known simply as instructions, though here with the addition of integers. There is a programmer-specified number of memory cells which can be navigated forward and backward, modified with numbers and arithmetic operations, tested for boolean values, printed and read into, and reset to the default value of 0.

To get started with SIMPL, run `git clone https://github.com/ashervahalik/simpl.git`, write a SIMPL file (or use one of the examples), and run `python3 simpl.py <filepath> <output>`. Provided there are no errors, a working binary will be generated at the path specified by `output`.

(Linux/Mac only) For more information, run `man ./simpl.1`. *(This is temporary until I can get SIMPL submitted to `brew` and `apt`, after which `man simpl` should just work.)*

If you find any weird bugs (which shouldn't happen often, but definitely could), please open an issue on the GitHub repository. I am also aware that this README and other documentation probably look like a mess to people that aren't me, so if something looks weird, just let me know.
## Compiler
The SIMPL compiler sets up memory cells according to the number specified in the program and checks all instructions in the code. Everything except for instructions and numbers is interpreted as a comment and ignored. A temporary file containing the SIMPL program transcribed to C is compiled with `gcc` and deleted, resulting in a final executable.

Currently, there is only a compiler written in Python (which is sticking around for portability), but a C++ version is in progress.
## Language
### Instructions
Here, square brackets `[]` specify optionals, and in code, they are used to contain comments.

- `<[num|{expr}]` and `>[num|{expr}]`: move `num` cells back or forward, if `num` is not specified then 1
- `+[num|{expr}]`: increment current cell by optional num, if `num` is not specified then 1
- `-[num|{expr}]`: same as `+` but decrements the current cell
- `({condition}sequence[|])`: evaluates `condition`; if true, executes `sequence`, otherwise continues; if `|` is present at the end of the sequence, it becomes a loop.
- `?[?]`: await character input; if `??`, the sum of the characters' ASCII values is added to the current cell; if `?`, each character's ASCII value is distributed to the next length(input) cells starting at the current cell
- `![!]`: print the value of the current cell; if `!`, then print integer value; if `!!`, then print ASCII value
- `:`: store the position of the current cell outside of the cell array
- `;`: recall the stored cell position
- `@`: reset the current cell to 0

### Expressions
In the context of expressions, `+` and `-` represent their respective arithmetic functions of plus and minus. In addition, `*` and `/` can be used to multiply and floor-divide. `==`, `<`, and `>` can be used to perform logical operations.
`#` will return the index of the current cell (with the cell array being 0-indexed) and can be used to perform math based on the current location in memory; `##` will return the total number of cells.
All expressions must be enclosed in curly brackets `{}`.
