from collections import Counter
import math
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ================= СПИСКИ КЛАССИФИКАЦИИ ОПЕРАТОРОВ =================

# 1. Слова-декларации (Полностью ИГНОРИРУЮТСЯ)
PERL_IGNORE_WORDS = {
    "my", "our", "local", "state", "sub", "use", "no", "package", 
    "require", "strict", "warnings", "constant"
}

# 2. Управляющие операторы (переходы)
CONTROL_NO_PAREN = {"return", "last", "next", "redo", "goto", "continue", "default"}

# 3. Составные операторы (if...elsif...else)
CHAIN_TRANSITIONS = {
    "if": {"elsif", "else"}, "unless": {"elsif", "else"}, "elsif": {"elsif", "else"},
    "try": {"catch", "finally"}, "catch": {"catch", "finally"}, "do": {"while", "until"},
    "while": {"continue"}, "until": {"continue"}, "for": {"continue"},
    "foreach": {"continue"}, "given": {"when", "default"}, "when": {"default"}
}
COMPOUND_KEYWORDS = set(CHAIN_TRANSITIONS.keys()) | {"else", "finally", "continue", "default"}

# 4. Синтаксические скобки, которые НЕ считаются за ()
SYNTACTIC_PAREN_KEYWORDS = {
    "if", "elsif", "unless", "while", "until", "for", "foreach", "given", "when", "catch"
}

# 5. Имена строковых и логических операций-слов (без скобок, аналог and/or/not/mod в Паскале)
PERL_WORD_OPERATORS = {
    "eq", "ne", "cmp", "lt", "gt", "le", "ge", "and", "or", "not", "xor", "x"
}

# 6. Имена процедур и встроенных функций (считаются с постфиксом ())
PERL_BUILTIN_FUNCS = {
    "print", "printf", "sprintf", "die", "warn", "push", "pop", "shift", "unshift", 
    "pos", "substr", "defined", "undef", "eval", "chomp", "chop", "chr", "crypt",
    "index", "lc", "lcfirst", "length", "ord", "pack", "reverse", "rindex",
    "uc", "ucfirst", "grep", "join", "map", "scalar", "sort", "unpack",
    "delete", "each", "exists", "keys", "values", "binmode", "close", "closedir",
    "eof", "fileno", "flock", "format", "getc", "open", "opendir", "read", "readdir",
    "readline", "rewinddir", "seek", "seekdir", "select", "syscall", "sysread", 
    "sysseek", "syswrite", "tell", "telldir", "truncate", "vec", "wait", "waitpid",
    "system", "exec", "kill", "chdir", "chmod", "chown", "chroot", "fcntl", "glob",
    "ioctl", "link", "lstat", "mkdir", "readlink", "rename", "rmdir", "stat", 
    "symlink", "sysopen", "umask", "unlink", "utime", "split", "abs", "int",
    "cos", "sin", "exp", "log", "sqrt", "rand", "srand", "time", "gmtime", "localtime"
}

PERL_ALL_KEYWORDS = (
    PERL_IGNORE_WORDS | CONTROL_NO_PAREN | COMPOUND_KEYWORDS | 
    SYNTACTIC_PAREN_KEYWORDS | PERL_WORD_OPERATORS | PERL_BUILTIN_FUNCS
)

PERL_MULTI_OPERATORS = [
    "...", "..", "<=>", "==", "!=", "=~", "!~", "<=", ">=",
    "&&", "||", "//", "->", "=>", "**=", "+=", "-=", "*=", "/=", 
    "%=", ".=", "x=", "|=", "&=", "^=", "**", "<<", ">>", "++", "--"
]

PERL_SINGLE_OPERATORS = [
    "+", "-", "*", "/", "%", "&", "^", "~", "!", "?", ":", ".", "<", ">", "=", "\\", "|"
]

PERL_BRACKET_PAIRS = {"(": ")", "[": "]", "{": "}"}

def _build_regex_alternation(items):
    escaped = sorted((re.escape(x) for x in items), key=len, reverse=True)
    return "|".join(escaped)

_MULTI_OP_RE = _build_regex_alternation(PERL_MULTI_OPERATORS)
_SINGLE_OP_RE = "[" + re.escape("".join(PERL_SINGLE_OPERATORS)) + "]"
_BRACKETS_OPEN_RE = "[" + re.escape("".join(PERL_BRACKET_PAIRS.keys())) + "]"
_BRACKETS_CLOSE_RE = "[" + re.escape("".join(PERL_BRACKET_PAIRS.values())) + "]"

def _tokenize(clean_code):
    token_patterns = [
        ("STRING",         r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''),
        ("REGEX_BIND",     r"=~\s*(?:s/(?:\\.|[^/])*/(?:\\.|[^/])*/[a-z]*|m?/(?:\\.|[^/])*/[a-z]*)"),
        ("READLINE",       r"<[A-Za-z_]*>"),
        ("VAR",            r"[\$\@\%][A-Za-z_]\w*|[\$\@\%]\{[A-Za-z_]\w*\}|[\$\@\%][\^\@_!~=+/|\\,.]"),
        ("NUMBER",         r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b|\b0[xX][0-9a-fA-F]+\b|\b0[bB][01]+\b"),
        ("LABEL",          r"^[ \t]*[A-Za-z_]\w*\s*:"),
        ("OP_MULTI",       _MULTI_OP_RE),
        ("SEMICOLON",      r";"),
        ("COMMA",          r","),
        ("BRACKET_OPEN",   _BRACKETS_OPEN_RE),
        ("BRACKET_CLOSE",  _BRACKETS_CLOSE_RE),
        ("OP_SINGLE",      _SINGLE_OP_RE),
        ("WORD",           r"\b[A-Za-z_]\w*\b"),
        ("SKIP",           r"[ \t\n\r]+"),
        ("MISC",           r"."),
    ]
    tok_regex = "|".join(f"(?P<{name}>{pattern})" for name, pattern in token_patterns)
    tokens = []
    
    for match in re.finditer(tok_regex, clean_code, re.MULTILINE):
        kind = match.lastgroup
        value = match.group()
        
        if kind == "SKIP":
            continue
            
        if kind == "REGEX_BIND":
            match_bind = re.match(r"(=~)\s*(.*)", value)
            tokens.append(("OP_MULTI", match_bind.group(1)))
            tokens.append(("REGEX", match_bind.group(2)))
            continue
            
        if kind == "READLINE":
            handle = match.group("READLINE")[1:-1].strip()
            tokens.append(("OP_MULTI", "<>"))
            if handle:
                tokens.append(("VAR", handle))
            continue
            
        tokens.append((kind, value.strip() if kind == "LABEL" else value))
    return tokens

def analyze_halstead(code_text):
    clean_lines = []
    for line in code_text.splitlines():
        line_no_comment = re.sub(r"#.*$", "", line)
        if re.match(r"^\s*(?:use|no|package|require)\b", line_no_comment):
            continue
        clean_lines.append(line_no_comment)
    clean_code = "\n".join(clean_lines)

    raw_tokens = _tokenize(clean_code)
    
    custom_funcs = set()
    for i in range(len(raw_tokens) - 1):
        if raw_tokens[i][0] == "WORD" and raw_tokens[i][1] == "sub":
            if raw_tokens[i+1][0] == "WORD":
                custom_funcs.add(raw_tokens[i+1][1])

    tokens = []
    for kind, value in raw_tokens:
        if kind == "LABEL": 
            continue
        if kind == "WORD" and value in PERL_IGNORE_WORDS: 
            continue
        tokens.append((kind, value))

    operators_list = []
    operands_list = []
    brace_depth = 0
    active_structs = {}
    paren_stack = [] 
    skip_next_word_as_label = False

    for i, (kind, value) in enumerate(tokens):
        if kind in ("STRING", "NUMBER", "VAR", "REGEX"):
            operands_list.append(value)
            continue

        if kind == "WORD":
            if skip_next_word_as_label:
                skip_next_word_as_label = False
                continue
                
            if value in ("goto", "last", "next", "redo"):
                operators_list.append(value)
                if i + 1 < len(tokens) and tokens[i+1][0] == "WORD" and tokens[i+1][1] not in PERL_ALL_KEYWORDS:
                    skip_next_word_as_label = True
                continue

            if value in CONTROL_NO_PAREN:
                operators_list.append(value)
                continue

            if value in COMPOUND_KEYWORDS:
                active = active_structs.get(brace_depth)
                if active and value in CHAIN_TRANSITIONS.get(active["last_keyword"], set()):
                    if active["name"] == "if...elsif...else":
                        active["last_keyword"] = value
                    else:
                        part = "..." + value
                        if part not in active["name"]:
                            active["name"] += part
                        active["last_keyword"] = value
                else:
                    canonical_name = "if...elsif...else" if value == "if" else value
                    obj = {"name": canonical_name, "last_keyword": value}
                    active_structs[brace_depth] = obj
                    operators_list.append(obj)
                    
            elif value in PERL_WORD_OPERATORS:
                operators_list.append(value)
            elif value in PERL_BUILTIN_FUNCS or value in custom_funcs:
                operators_list.append(value + "()")
            else:
                operands_list.append(value)

        elif kind == "BRACKET_OPEN":
            if value == "(":
                prev_word = tokens[i-1][1] if i > 0 and tokens[i-1][0] == "WORD" else None
                    
                if prev_word in SYNTACTIC_PAREN_KEYWORDS:
                    paren_stack.append("SYNTAX")
                elif prev_word in PERL_BUILTIN_FUNCS or prev_word in custom_funcs:
                    paren_stack.append("FUNC")
                else:
                    paren_stack.append("GROUPING")
                    operators_list.append("()")
            elif value == "{":
                brace_depth += 1
                operators_list.append("{}") 
            elif value == "[":
                operators_list.append("[]")

        elif kind == "BRACKET_CLOSE":
            if value == ")":
                if paren_stack:
                    paren_stack.pop()
            elif value == "}":
                active_structs.pop(brace_depth, None)
                brace_depth = max(0, brace_depth - 1)

        elif kind == "SEMICOLON":
            active_structs.pop(brace_depth, None)
            operators_list.append(";")

        elif kind in ("OP_MULTI", "OP_SINGLE", "COMMA"):
            operators_list.append(value)

    final_operators = [op["name"] if isinstance(op, dict) else op for op in operators_list]

    op_freq = Counter(final_operators)
    operand_freq = Counter(operands_list)

    n1 = len(op_freq)
    n2 = len(operand_freq)
    N1 = len(final_operators)
    N2 = len(operands_list)

    eta = n1 + n2
    N = N1 + N2
    V = N * math.log2(eta) if eta > 0 else 0

    return {
        "op_freq": op_freq, "operand_freq": operand_freq,
        "n1": n1, "n2": n2, "N1": N1, "N2": N2, "eta": eta, "N": N, "V": V,
    }

class HalsteadApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Анализатор Метрик Холстеда")
        self.root.geometry("900x650")

        file_frame = ttk.Frame(self.root, padding=10)
        file_frame.pack(fill=tk.X)

        ttk.Label(file_frame, text="Файл:").pack(side=tk.LEFT, padx=5)
        self.file_path_var = tk.StringVar()
        self.file_entry = ttk.Entry(file_frame, textvariable=self.file_path_var, width=60)
        self.file_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        browse_btn = ttk.Button(file_frame, text="Выбрать файл...", command=self.browse_file)
        browse_btn.pack(side=tk.LEFT, padx=5)

        calc_btn = ttk.Button(file_frame, text="Рассчитать", command=self.run_analysis)
        calc_btn.pack(side=tk.LEFT, padx=5)

        tables_frame = ttk.Frame(self.root, padding=10)
        tables_frame.pack(fill=tk.BOTH, expand=True)

        op_frame = ttk.LabelFrame(tables_frame, text="Операторы (f1j)", padding=5)
        op_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.op_tree = ttk.Treeview(op_frame, columns=("j", "operator", "f1j"), show="headings", height=15)
        self.op_tree.heading("j", text="j")
        self.op_tree.heading("operator", text="Оператор")
        self.op_tree.heading("f1j", text="Частота (f1j)")
        self.op_tree.column("j", width=40, anchor="center")
        self.op_tree.column("operator", width=220, anchor="w")
        self.op_tree.column("f1j", width=80, anchor="center")
        self.op_tree.pack(fill=tk.BOTH, expand=True)

        operand_frame = ttk.LabelFrame(tables_frame, text="Операнды (f2i)", padding=5)
        operand_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        self.operand_tree = ttk.Treeview(operand_frame, columns=("i", "operand", "f2i"), show="headings", height=15)
        self.operand_tree.heading("i", text="i")
        self.operand_tree.heading("operand", text="Операнд")
        self.operand_tree.heading("f2i", text="Частота (f2i)")
        self.operand_tree.column("i", width=40, anchor="center")
        self.operand_tree.column("operand", width=180, anchor="w")
        self.operand_tree.column("f2i", width=80, anchor="center")
        self.operand_tree.pack(fill=tk.BOTH, expand=True)

        results_frame = ttk.LabelFrame(self.root, text="Результаты расчёта метрик Холстеда", padding=10)
        results_frame.pack(fill=tk.X, padx=15, pady=10)

        self.lbl_n1 = ttk.Label(results_frame, text="Словарь операторов (η1): —")
        self.lbl_n1.grid(row=0, column=0, sticky="w", padx=15, pady=2)

        self.lbl_n2 = ttk.Label(results_frame, text="Словарь операндов (η2): —")
        self.lbl_n2.grid(row=0, column=1, sticky="w", padx=15, pady=2)

        self.lbl_N1 = ttk.Label(results_frame, text="Число операторов (N1): —")
        self.lbl_N1.grid(row=1, column=0, sticky="w", padx=15, pady=2)

        self.lbl_N2 = ttk.Label(results_frame, text="Число операндов (N2): —")
        self.lbl_N2.grid(row=1, column=1, sticky="w", padx=15, pady=2)

        self.lbl_eta = ttk.Label(results_frame, text="Словарь программы (η = η1 + η2): —")
        self.lbl_eta.grid(row=2, column=0, sticky="w", padx=15, pady=2)

        self.lbl_N = ttk.Label(results_frame, text="Длина программы (N = N1 + N2): —")
        self.lbl_N.grid(row=2, column=1, sticky="w", padx=15, pady=2)

        self.lbl_V = ttk.Label(results_frame, text="Объём программы (V = N log2 η): —")
        self.lbl_V.grid(row=3, column=0, columnspan=2, sticky="w", padx=15, pady=5)

    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="Выберите файл исходного кода",
            filetypes=[("Perl Scripts", "*.pl *.pm"), ("Text/All Files", "*.*")],
        )
        if filename:
            self.file_path_var.set(filename)

    def run_analysis(self):
        path = self.file_path_var.get()
        if not path or not os.path.isfile(path):
            messagebox.showerror("Ошибка", "Пожалуйста, выберите корректный файл.")
            return

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()

            res = analyze_halstead(code)

            for item in self.op_tree.get_children():
                self.op_tree.delete(item)
            for item in self.operand_tree.get_children():
                self.operand_tree.delete(item)

            for idx, (op, count) in enumerate(res["op_freq"].most_common(), start=1):
                self.op_tree.insert("", "end", values=(idx, op, count))

            for idx, (operand, count) in enumerate(res["operand_freq"].most_common(), start=1):
                self.operand_tree.insert("", "end", values=(idx, operand, count))

            self.lbl_n1.config(text=f"Словарь операторов (η1): {res['n1']}")
            self.lbl_n2.config(text=f"Словарь операндов (η2): {res['n2']}")
            self.lbl_N1.config(text=f"Число операторов (N1): {res['N1']}")
            self.lbl_N2.config(text=f"Число операндов (N2): {res['N2']}")
            self.lbl_eta.config(text=f"Словарь программы (η = η1 + η2): {res['eta']}")
            self.lbl_N.config(text=f"Длина программы (N = N1 + N2): {res['N']}")
            self.lbl_V.config(text=f"Объём программы (V = N log2 η): {res['V']:.2f} бит")

        except Exception as e:
            messagebox.showerror("Ошибка обработки", f"Не удалось проанализировать файл:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = HalsteadApp(root)
    root.mainloop()