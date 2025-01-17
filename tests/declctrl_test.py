from typing import Union
import ujson
import pytest

import pyaici
import pyaici.rest
import pyaici.util
import pyaici.ast as ast

model_name = "microsoft/Orca-2-13b"


def wrap(text):
    return pyaici.util.orca_prompt(text)


def greedy_query(prompt: str, steps: list):
    ast_module = pyaici.rest.ast_module
    temperature = 0.0
    assert ast_module
    if prompt:
        steps = [ast.fixed(prompt)] + steps
    res = pyaici.rest.run_controller(
        controller=ast_module,
        controller_arg={"steps": steps},  # type: ignore
        temperature=temperature,
        max_tokens=200,
    )
    if res["error"]:
        pytest.fail(res["error"])
    return res["text"]


def expect(expected: Union[list[str], str], prompt: str, steps: list):
    if isinstance(expected, str):
        expected = [expected]
    res = greedy_query(prompt, steps)
    if expected[-1] == "*":
        expected.pop()
        res = res[0 : len(expected)]
    if len(res) != len(expected):
        pytest.fail(f"query output length mismatch {len(res)} != {len(expected)}")
    for i in range(len(res)):
        # ░ is used as a placeholder; will be removed
        r: str = res[i]
        r = r.replace("░", "").rstrip(" ")
        r2 = r
        e = expected[i]
        if e.startswith("<...>") and len(r) > len(e) - 5:
            e = e[5:]
            r2 = r2[-len(e) :]
        if r2 != e:
            if len(r) > 40:
                print("GOT", f'"""{r}"""')
            else:
                print("GOT", ujson.dumps(r))
            pytest.fail(f"query output mismatch at #{i}")


def test_hello():
    expect(
        "Hello, I am",
        "Hello",
        [ast.gen(max_tokens=3)],
    )


def test_gen_num():
    expect(
        "I am about 10 years and 10 months.",
        "",
        [
            ast.fixed("I am about "),
            ast.gen(max_tokens=2, rx=r"\d+"),
            ast.fixed(" years and "),
            ast.gen(max_tokens=2, rx=r"\d+"),
            ast.fixed(" months."),
        ],
    )


def test_grammar():
    expect(
        """<...>```
int fib(int n) {
    if (n == 1) {
        return 1;
    }
    if (n == 2) {
        return 2;
    }
    return fib(n - 1) + fib(n - 2);
}""",
        wrap("Write fib function in C"),
        [
            ast.fixed("```\n"),
            ast.gen(
                yacc=open("aici_abi/grammars/c.y").read(),
                # rx="#include(.|\n)*",
                stop_at="\n}",
                max_tokens=100,
            ),
        ],
    )


json_template = {
    "name": "",
    "valid": True,
    "description": "",
    "type": "foo|bar|baz|something|else",
    "address": {"street": "", "city": "", "state": "[A-Z][A-Z]"},
    "age": 1,
    "fraction": 1.5,
}


def test_json():
    expect(
        """<...>assistant
{
"name":"J. Random Hacker",
"valid":true,
"description":"J. Random Hacker is a talented and creative individual based in Seattle, Washington. With a passion for technology and a kn",
"type":"something",
"address":{
"street":"123 Hacker St",
"city":"Seattle",
"state":"WA"
},
"age":25,
"fraction":0.5
}""",
        wrap("Write about J. Random Hacker from Seattle"),
        ast.json_to_steps(json_template),
    )


# def test_json_N():
#     results = greedy_query(
#         wrap("About J.R.R.Tolkien"), ast.json_to_steps(json_template), n=5
#     )
#     assert len(results) == 5
#     for r in results:
#         obj = ujson.loads(r)
#         for key in json_template.keys():
#             assert key in obj


def test_ff_0():
    expect(
        "Hello, 3 + 8 = 11",
        "Hello",
        [
            {"Gen": {"rx": ", ", "max_tokens": 10}},
            {"Fixed": {"text": {"String": {"str": "3 + 8 ="}}}},
            {"Gen": {"max_tokens": 5}},
        ],
    )


def test_ff_1():
    expect(
        "Hello, 7 + 8 = 15",
        "Hello",
        [
            ast.gen(rx=", "),
            ast.fixed("7 + 8 ="),
            ast.gen(rx=r" \d+"),
        ],
    )


def test_ff_2():
    expect(
        "Hello, 7 + 8 = 15",
        "Hello",
        [
            ast.gen(rx=", "),
            ast.fixed("7 + 8"),
            ast.gen(rx=r" = \d+"),
        ],
    )


def check_mask(expected, mask_tags):
    expect(
        expected,
        "The word 'hello' in",
        [
            ast.fixed(" French is", tag="lang"),
            ast.gen(max_tokens=5, mask_tags=mask_tags),
        ],
    )


def disabled_test_mask_1():
    check_mask(" French is 'hello world' is", ["lang"])


def disabled_test_mask_2():
    check_mask(" French is 'bonjour'.", [])


def test_fork_1():
    expect(
        [
            "The word 'hello' in French is 'bonjour'.",
            "The word 'hello' in Spanish is 'hola'.\n",
        ],
        "",
        [
            ast.fixed("The word 'hello' in"),
            ast.fork(
                [
                    ast.fixed(" French is"),
                    ast.gen(max_tokens=5),
                ],
                [
                    ast.fixed(" Spanish is"),
                    ast.gen(max_tokens=5),
                ],
            ),
        ],
    )


def test_backtrack_1():
    for french in [
        " in French is translated as",
        " French",
        " in French is",
        " in Paris is",
    ]:
        expect(
            "<...>Results: 'bonjour' 'hi'",
            "",
            [
                ast.fixed("The word 'hello'"),
                ast.label("lang", ast.fixed(french)),
                ast.gen(rx=r" '[^'\.]*'", max_tokens=15, set_var="french"),
                ast.fixed(" or", following="lang"),
                ast.gen(rx=r" '[^'\.]*'", max_tokens=15, set_var="blah"),
                ast.fixed("\nResults:{{french}}{{blah}}", expand_vars=True),
            ],
        )


def test_backtrack_2():
    expect(
        "<...>Foo\nZzzzz\nQux\nMux\nDONE",
        "",
        [
            ast.fixed("Please remember the following items:\nFoo\nZzzzz"),
            ast.label("l", ast.fixed("\nBar\nBaz")),
            ast.fixed("\nPlease repeat the list, say DONE when done:\n"),
            ast.gen(max_tokens=20, stop_at="DONE", set_var="x"),
            ast.fixed(
                "\nQux\nMux\nPlease repeat the list, say DONE when done:\n",
                following="l",
            ),
            ast.gen(max_tokens=20, stop_at="DONE", set_var="y"),
        ],
    )


def test_inner_1():
    expect(
        "<...><city>Poznań</city> is a vibrant city in western Poland, known for its rich history, beautiful",
        "",
        [
            ast.fixed(pyaici.util.orca_prefix),
            # there is currently a bug going back to the first token, so we label the stuff after [INST] instead
            ast.label(
                "start",
                ast.fixed(
                    "List 5 names of cities in Poland. Use <city>City Name</city> syntax. Say DONE when done."
                    + pyaici.util.orca_suffix
                ),
            ),
            ast.gen(
                max_tokens=100,
                stop_at="DONE",
                set={
                    "cities": ast.e_extract_all(
                        r"<city>([^<]*</city>)", ast.e_current()
                    )
                },
            ),
            ast.fixed(
                "Pick a specific city and say something about it. "
                "Wrap city names in <city></city>, for example <city>London</city>." 
                  + pyaici.util.orca_suffix,
                # backtrack to start, to erase info about 'Poland'
                following="start",
            ),
            ast.gen(
                max_tokens=20,
                inner={
                    "<city>": ast.e_var("cities"),
                },
            ),
        ],
    )


def test_wait_1():
    expect(
        [
            """The word 'hello' in
french: 'bonjour.'
spanish: 'hola.'
""",
            "*",
        ],
        "",
        [
            ast.fixed("The word 'hello' in"),
            ast.fork(
                [
                    ast.fixed("\n"),
                    ast.wait_vars("french", "spanish"),
                    ast.fixed(
                        "french:{{french}}\nspanish:{{spanish}}\n", expand_vars=True
                    ),
                ],
                [
                    ast.fixed(" Spanish is"),
                    ast.gen(rx=r" '[^']*'", max_tokens=15, set_var="spanish"),
                ],
                [
                    ast.fixed(" French is"),
                    ast.gen(rx=r" '[^']*'", max_tokens=15, set_var="french"),
                ],
            ),
        ],
    )
