from dataclasses import dataclass       # for tokens
from typing import Optional             # also for tokens
from tempfile import NamedTemporaryFile # for outputted, uncompiled C code
from sys import argv                    # use CLI args for file input
import subprocess                       # for running gcc on uncompiled C
from os import unlink                   # for deleting temp file

# Check args are correct
execname = argv[0]
if len(argv) < 2 and len(argv) < 3:
	print(f"{execname}: expected filepath and compiled_name or switch")
	exit(1)
elif len(argv) < 2:
	print(f"{execname}: expected filepath")
	exit(1)
elif len(argv) < 3:
	print(f"{execname}: expected compiled_name or switch")
	exit(1)
else:
	compiled_name = argv[2]


# Check that the file exists
filepath = argv[1]
try:
	with open(filepath, "r") as _:
		pass
except FileNotFoundError:
	print(f"{execname}: {filepath}: no such file")
	exit(1)

# Check that it's a valid file
if ".simpl" not in filepath:
	print(f"{execname}: {filepath} is not a valid SIMPL file")

# Read file
source_code = str()
with open(filepath, "r") as file:
	source_code = file.read()

def preprocess(source: str) -> str | None: # type: ignore[return]
	"""Preprocess `source`, removing comments and newlines."""
	result: list[str] = []
	depth: int = 0
	global errors
	for i, char in enumerate(source):
		if char == '[':
			depth += 1
		elif char == ']':
			if depth == 0:
				raise SyntaxError(f"Unexpected ']' at position {i}")
				break
			depth -= 1
		elif depth == 0 and char not in ' \r\n\t':
			result.append(char)
	if depth != 0:
		raise SyntaxError(f"Unmatched '['")
	else:
		return ''.join(result)


@dataclass
class Token:
	"""Token class"""
	type: str
	payload: Optional[str | int] = None

	def __str__(self) -> str:
		return f"{self.type}{f'({self.payload})' if self.payload else ''}"


class Tokenizer:
	"""SIMPL Tokenizer for use in `parse()`"""

	def __init__(self, source: str):
		"""Tokenizer initializer"""
		self.source = source
		self.cursor = 0

	def peek(self, offset: int = 0) -> str | None:
		"""Peek ahead by `offset` characters and return the character unless EOF then None."""
		return self.source[self.cursor + offset] if self.cursor + offset < len(self.source) else None

	def consume(self) -> str | None:
		"""Generic consume; used in all other consume methods."""
		char = self.peek()
		self.cursor += 1
		return char

	def consume_num(self) -> int | None:
		"""Consume a run of digits as a number, returning str(number) or None."""
		num_str = ""
		while self.peek() is not None and self.peek().isdigit(): # type: ignore[union-attr]
			num_str += self.consume() # type: ignore[operator]
		return int(num_str) if num_str else None

	def consume_expr(self) -> str:
		"""Consume {}-enclosed expression and return the inner string."""
		assert self.consume() == '{'
		depth = 1
		expr = ''
		while True:
			char = self.consume()
			if char is None:
				raise SyntaxError(f"Unmatched '{{' at {self.cursor}")
			if char == '{':
				depth += 1
			elif char == '}':
				depth -= 1
				if depth == 0:
					break
				if depth < 0:
					raise SyntaxError(f"Unexpected '}}' at {self.cursor}")
			expr += char
		return expr

	def consume_payload(self) -> int | str | None:
		"""Consume an optional payload after an instruction."""
		if self.peek() == '{':
			return self.consume_expr()
		return self.consume_num()

	def odd_number_of(self, check: str) -> bool:
		"""Check whether there is an odd number of `check`."""
		counter = 1
		i = 0
		while self.peek(i) == check:
			i += 1
		if i % 2 != 0:
			return False
		return True 

	def tokenize(self) -> list[Token]:
		"""Tokenize the source code and return a list of Tokens."""
		tokens: list[Token] = []
		while self.cursor < len(self.source):
			# Consume, advancing the cursor
			char = self.consume()
			# Memory size instruction
			if char == '~':
				if not self.peek().isdigit(): # type: ignore[union-attr]
					raise SyntaxError(f"Expected number to define memory size at {self.cursor}")
				if not self.cursor <= 1:
					raise SyntaxError(f"Memory size must be defined at the beginning of the file; got memory size definition at {self.cursor}")
				tokens.append(Token('MEMSIZE', self.consume_num() or 1))
			# Move right
			elif char == '>':
				tokens.append(Token('MVRIGHT', self.consume_payload() or 1))
			# Move left
			elif char == '<':
				tokens.append(Token('MVLEFT', self.consume_payload() or 1))
			# Increment cell
			elif char == '+':
				tokens.append(Token('INC', self.consume_payload() or 1))
			# Decrement cell
			elif char == '-':
				tokens.append(Token('DEC', self.consume_payload() or 1))
			# Begin conditional
			elif char == '(':
				if self.peek() == ')':
					raise SyntaxError(f"Unexpected ')' at {self.cursor}: conditionals must not be empty")
				if self.peek() != '{':
					raise SyntaxError(f"Expected '{{' to begin conditional expression at {self.cursor}, got {self.peek()}")
				tokens.append(Token('LPAREN', self.consume_expr()))
			# Loop conditional
			elif char == '|':
				if self.peek() != ')':
					raise SyntaxError(f"Unexpected '|' at {self.cursor}")
				tokens.append(Token('PIPE'))
			# End conditional
			elif char == ')':
				tokens.append(Token('RPAREN'))
			# Input
			elif char == '?':
				if self.peek() == '{':
					raise SyntaxError(f"Unexpected expression after '?' at {self.cursor}")
				if self.peek() == '?':
					if self.odd_number_of(char):
						raise SyntaxError(f"Instruction '{char}' does not support odd-numbered sequences")
					self.consume()
					tokens.append(Token('INPUTSUM'))
				else:
					tokens.append(Token('INPUTDIST'))
			# Output
			elif char == '!':
				if self.peek() == '{':
					raise SyntaxError(f"Unexpected expression after '!' at {self.cursor}")
				if self.peek() == '!':
					if self.odd_number_of(char):
						raise SyntaxError(f"Instruction '{char}' does not support odd-numbered sequences")
					self.consume()
					tokens.append(Token('PRINTCHAR'))
				else:
					tokens.append(Token('PRINTINT'))
			# Store cell pos
			elif char == ':':
				if self.peek() == '{':
					raise SyntaxError(f"Unexpected expression after ':' at {self.cursor}")
				tokens.append(Token('STOREPOS'))
			# Recall cell pos
			elif char == ';':
				if self.peek() == '{':
					raise SyntaxError(f"Unexpected expression after ';' at {self.cursor}")
				tokens.append(Token('RECALLPOS'))
			# Reset cell
			elif char == '@':
				if self.peek() == '{':
					raise SyntaxError(f"Unexpected expression after '@' at {self.cursor}")
				tokens.append(Token('RESET'))
			# Get cell value/total cell count
			elif char == '#':
				if self.peek() == '{':
					raise SyntaxError(f"Unexpected expression after '#' at {self.cursor}")
				if self.peek() == '#':
					self.consume()
					tokens.append(Token('GETTOTALCELL'))
				else:
					tokens.append(Token('GETCELLVAL'))
			else:
				raise SyntaxError(f"Unexpected '{char}' at {self.cursor}")
		return tokens


def tokenize(source: str) -> list[Token]:
	"""Convenience wrapper for Tokenizer"""
	return Tokenizer(source).tokenize()


def match_parentheses(tokens: list[Token]) -> dict:
	"""Match parentheses and determine which conditionals are loops."""
	stack: list = []
	match_table: dict = {}
	for i, token in enumerate(tokens):
		if token.type == 'LPAREN':
			stack.append(i)
		elif token.type == 'RPAREN':
			if not stack:
				raise SyntaxError(f"Unmatched ')' at token {i}")
			j = stack.pop()
			is_loop = tokens[i - 1].type == 'PIPE'
			match_table[j] = (i, is_loop)
			match_table[i] = (j, is_loop)
	if stack:
		raise SyntaxError(f"Unmatched '(' at token {stack[-1]}")
	return match_table


class ExprParser:
	"""Expression parser for evaluating {}-expression payloads"""

	def __init__(self, source: str) -> None:
		"""Initialize the ExprParser"""
		self.source = source
		self.cursor = 0

	def peek(self, offset: int = 0) -> str | None:
		"""Peek ahead by `offset` characters and return character unless EOF then None."""
		i = self.cursor + offset
		return self.source[i] if i < len(self.source) else None

	def consume(self) -> str:
		"""Consume the current character and return it, advancing the cursor."""
		char = self.peek()
		self.cursor += 1
		return char # type: ignore[return-value]

	def parse(self) -> str:
		"""Parsing entrypoint, returning a C expression."""
		result = self.parse_comp()
		if self.cursor < len(self.source):
			raise SyntaxError(f"Unexpected '{self.peek()}' in expression {self.source}")
		return result

	def parse_comp(self) -> str:
		"""Parse low-precedence comparison ops: <, >, <=, >=, ==, !="""
		left = self.parse_add()
		ops = ['<', '>', '<=', '>=', '==', '!=']
		for op in ops:
			if self.source[self.cursor:self.cursor + len(op)] == op:
				self.cursor += len(op)
				right = self.parse_add()
				return f"({left} {op} {right})"
		return left

	def parse_add(self) -> str:
		"""Parse medium-precedence addition ops: +, -"""
		left = self.parse_mult()
		while self.peek() in ('+', '-'):
			op = self.consume()
			right = self.parse_mult()
			left = f"({left} {op} {right})"
		return left

	def parse_mult(self) -> str:
		"""Parse high-precedence multiplication ops: *, /"""
		left = self.parse_unary()
		while self.peek() in ('*', '/'):
			op = self.consume()
			right = self.parse_unary()
			left = f"({left} {op} {right})"
		return left

	def parse_unary(self) -> str:
		"""Parse unary minus."""
		if self.peek == '-':
			self.consume()
			operand = self.parse_primary()
			return f"(-{operand})"
		return self.parse_primary()

	def parse_primary(self) -> str:
		"""Parse terminals (;, #, ##) and integer literals."""
		if self.source[self.cursor:self.cursor + 2] == '##': # GETTOTALCELL
			self.cursor += 2
			return "CELL_COUNT" # this will be #defined in the resulting code
		if self.peek() == '#':  # GETCELLVAL
			self.consume()
			return "mem->data[mem->sel]"
		if self.peek() == ';':  # RECALLPOS
			self.consume()
			return "stored"
		if self.peek() is not None and (self.peek().isdigit() or self.peek() == '-'): # type: ignore[union-attr]
			num_str = ''
			if self.peek() == '-':
				num_str += self.consume()
			while self.peek() is not None and self.peek().isdigit(): # type: ignore[union-attr]
				num_str += self.consume()
			return num_str
		raise SyntaxError(f"Unexpected '{self.peek()}' in expression '{self.source}'")


def parse_expr(source: str) -> str:
	"""Convenience wrapper for ExprParser"""
	return ExprParser(source).parse()


def generate_code(tokens: list[Token], match_table: dict) -> list[str]:
	"""Generate the C code to be compiled. Only the functions required by the program are stored in the generated code."""
	lines: list[str] = []
	indent: int = 1

	def emit(line: str):
		"""Insert new line with current indentation."""
		lines.append("\t" * indent + line)

	def resolve(payload) -> str:
		"""Resolve expression payload into a proper C expression."""
		if isinstance(payload, int):
			return str(payload)
		if isinstance(payload, str):
			return parse_expr(payload)
		raise ValueError(f"Unexpected payload type for '{payload}'")

	cell_count: int = 128
	uses_inputdist = False
	uses_inputsum = False
	uses_printint = False
	uses_printchar = False
	for token in tokens:
		match token.type:
			case 'MEMSIZE':
				if int(token.payload) > 50_000_000: # type: ignore[arg-type]
					raise ValueError(f"No more than 50,000,000 memory cells allowed per program; program specified {token.payload:,}")
				cell_count = int(token.payload) # type: ignore[arg-type]
			case 'INPUTSUM':
				if uses_inputsum: continue
				uses_inputsum = True
			case 'INPUTDIST':
				if uses_inputdist: continue
				uses_inputdist = True
			case 'PRINTINT':
				if uses_printint: continue
				uses_printint = True
			case 'PRINTCHAR':
				if uses_printchar: continue
				uses_printchar = True
	c_header = f"""\
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CELL_COUNT {cell_count}
typedef struct {{
	int *data;
	int sel;
}} Mem;
// Initialize memory
Mem *initMem(int length) {{
	Mem *newMem = (Mem*)malloc(sizeof(Mem));
	newMem->data = (int*)malloc(length * sizeof(int));
	for (int i = 0; i < length; i++) newMem->data[i] = 0;
	return newMem;
}}
// Free memory (called at program end)
void freeMem(Mem* memory) {{ free(memory->data); free(memory); }}
"""
	if uses_inputdist:
		c_header += """\
// Get input and distribute across cells
void inputDist(Mem* memory) {
	char buf[CELL_COUNT];
	fgets(buf, sizeof(buf), stdin);
	buf[strcspn(buf, "\\n")] = '\\0';
	for (int i = 0; i < strlen(buf); i++) memory->data[memory->sel + i] = buf[i];
}
"""
	if uses_inputsum:
		c_header += """\
// Get input and set the sum of its ASCII values into the current cell
void inputSum(Mem* memory) {
	char buf[CELL_COUNT];
	fgets(buf, sizeof(buf), stdin);
	buf[strcspn(buf, "\\n")] = '\\0';
	int sum = 0;
	for (int i = 0; i < strlen(buf); i++) sum += (int)buf[i];
	memory->data[memory->sel] = sum;
}
"""
	if uses_printint:
		c_header += """\
void printInt(Mem* memory) {
	printf("%d", memory->data[memory->sel]);
}
"""
	if uses_printchar:
		c_header += """\
void printChar(Mem* memory) {
	printf("%c", memory->data[memory->sel]);
}
"""

	lines.append(c_header)
	lines.append("int main() {")
	emit("Mem *mem = initMem(CELL_COUNT);")
	emit("int stored = 0;")
	lines.append("")
	emit("// Program start")

	# This is where the fun stuff begins...
	i = 0
	while i < len(tokens):
		token = tokens[i]
		if token.type == 'MVRIGHT':
			emit(f"mem->sel += {resolve(token.payload)};")
		elif token.type == 'MVLEFT':
			emit(f"mem->sel -= {resolve(token.payload)};")
		elif token.type == 'INC':
			emit(f"mem->data[mem->sel] += {resolve(token.payload)};")
		elif token.type == 'DEC':
			emit(f"mem->data[mem->sel] -= {resolve(token.payload)};")
		elif token.type == 'RESET':
			emit(f"mem->data[mem->sel] = 0;")
		elif token.type == 'STOREPOS':
			emit(f"stored = mem->sel;")
		elif token.type == 'RECALLPOS':
			emit(f"mem->sel = stored;") # Claude actually came up with this and I like it
		elif token.type == 'GETCELLVAL':
			raise SyntaxError(f"Unexpected '#' outside expression context")
		elif token.type == 'GETTOTALCELL':
			raise SyntaxError(f"Unexpected '##' outside expression context")
		elif token.type == 'INPUTDIST':
			emit(f"inputDist(mem);")
		elif token.type == 'INPUTSUM':
			emit(f"inputSum(mem);")
		elif token.type == 'PRINTINT':
			emit(f"printInt(mem);")
		elif token.type == 'PRINTCHAR':
			emit(f"printChar(mem);")
		elif token.type == 'LPAREN':
			rparen_idx, is_loop = match_table[i]
			condition = resolve(token.payload)
			if is_loop:
				emit(f"while ({condition}) {{")
			else:
				emit(f"if ({condition}) {{")
			indent += 1
		elif token.type == 'PIPE':
			pass # only used in the tokenizer and paren matcher
		elif token.type == 'RPAREN':
			indent -= 1
			emit("}")
		elif token.type == 'MEMSIZE':
			i += 1
			continue
		else:
			raise SyntaxError(f"Unknown token type {token.type}")
		i += 1
	emit("// End program")
	lines.append("")
	emit("freeMem(mem);")
	emit("return 0;")
	lines.append("}")
	return lines


def compile(code: list[str], /, compiler: str = "gcc") -> None:
	# with NamedTemporaryFile("r", suffix=".c", prefix="simpl-", delete=False) as file:
	# 	for line in code:
	# 		file.write(f"{line}\n")
	# 	fname = file.name
	with open("simplcomp.c", "w") as file:
		for line in code:
			file.write(f"{line}\n")
	subprocess.run([compiler, "-Wno-parentheses", "simplcomp.c", "-o", compiled_name])
	unlink("simplcomp.c")


def main(source: str) -> int:
	# Always run preprocessor
	global filepath
	if not isinstance(preprocessed := preprocess(source), str):
		raise RuntimeError(f"Could not preprocess {filepath}")
	# Preprocessor only
	if compiled_name == '-E':
		print(preprocessed)
		return 0
	tokens = tokenize(preprocessed) # type: ignore[arg-type]
	# Up to tokenizer
	if compiled_name == '-T':
		print(*tokens, sep=', ', end='.\n')
		return 0
	# Up to C transpiler
	match_table: dict = match_parentheses(tokens)
	c_transpiled: list[str] = generate_code(tokens, match_table)
	if compiled_name == '-S':
		print(*c_transpiled, sep="\n")
		return 0
	# Unrecognized switch
	if compiled_name[0] == '-':
		print(f"{execname}: unrecognized switch '{compiled_name}'")
	# Complete the full compilation pipeline
	compile(c_transpiled)
	return 0


if __name__ == '__main__':
	try:
		exit_code = main(source_code)
		if exit_code == 1:
			print(f"Use 'man ./simpl.1' to view compiler + language documentation.")
		exit(exit_code)
	except SyntaxError as e:
		print(f"SyntaxError: {e}")
	except RuntimeError as e:
		print(f"RuntimeError: {e}")
	except ValueError as e:
		print(f"ValueError: {e}")
	except Exception as e:
		print(f"Generic Exception: {e}")
