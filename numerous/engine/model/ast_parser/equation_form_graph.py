import ast
from numerous.engine.model.graph_representation.utils import EdgeType
from numerous.engine.model.graph_representation import MappingsGraph, Graph
from numerous.engine.model.utils import wrap_function


def node_to_ast(n: int, g: MappingsGraph, var_def, ctxread=False, read=True):
    nk = g.key_map[n]
    try:
        if (na := g.get(n, 'ast_type')) == ast.Attribute:

            return var_def(nk, ctxread, read)

        elif na == ast.Name:
            return var_def(nk, ctxread, read)

        elif na == ast.Num:
            return ast.Call(args=[ast.Num(value=g.get(n, 'value'),
                                          lineno=0, col_offset=0)], func=ast.Name(id='float64', lineno=0, col_offset=0,
                                                                                  ctx=ast.Load()),
                            keywords=[], lineno=0, col_offset=0)

        elif na == ast.BinOp:

            left_node = g.get_edges_for_node_filter(end_node=n, attr='e_type', val=EdgeType.LEFT)[1][0][0]

            left_ast = node_to_ast(left_node, g, var_def, ctxread=ctxread)

            right_node = g.get_edges_for_node_filter(end_node=n, attr='e_type', val=EdgeType.RIGHT)[1][0][0]

            right_ast = node_to_ast(right_node, g, var_def, ctxread=ctxread)

            ast_binop = ast.BinOp(left=left_ast, right=right_ast, op=g.get(n, 'ast_op'), lineno=0, col_offset=0)
            return ast_binop

        elif na == ast.UnaryOp:
            operand = g.get_edges_for_node_filter(end_node=n, attr='e_type', val=EdgeType.OPERAND)[1][0][0]

            operand_ast = node_to_ast(operand, g, var_def, ctxread=ctxread)

            ast_unop = ast.UnaryOp(operand=operand_ast, op=g.get(n, 'ast_op'), lineno=0, col_offset=0)
            return ast_unop

        elif na == ast.Call:

            args = [ii[0] for ii in g.get_edges_for_node_filter(end_node=n, attr='e_type', val=EdgeType.ARGUMENT)[1]]
            args_ast = []
            for a in args:
                a_ast = node_to_ast(a, g, var_def, ctxread=ctxread)
                args_ast.append(a_ast)

            ast_Call = ast.Call(args=args_ast, func=g.get(n, 'func'), keywords=[], lineno=0, col_offset=0)

            return ast_Call

        elif na == ast.IfExp:

            body = g.get_edges_for_node_filter(end_node=n, attr='e_type', val=EdgeType.BODY)[1][0][0]
            body_ast = node_to_ast(body, g, var_def, ctxread=ctxread)

            orelse = g.get_edges_for_node_filter(end_node=n, attr='e_type', val=EdgeType.ORELSE)[1][0][0]
            orelse_ast = node_to_ast(orelse, g, var_def, ctxread=ctxread)

            test = g.get_edges_for_node_filter(end_node=n, attr='e_type', val=EdgeType.TEST)[1][0][0]
            test_ast = node_to_ast(test, g, var_def, ctxread=ctxread)

            ast_ifexp = ast.IfExp(body=body_ast, orelse=orelse_ast, test=test_ast, lineno=0, col_offset=0)

            return ast_ifexp

        elif na == ast.Compare:
            comp = [ii[0] for ii in g.get_edges_for_node_filter(end_node=n, attr='e_type', val=EdgeType.COMP)[1]]
            comp_ast = []
            for a in comp:
                a_ast = node_to_ast(a, g, var_def, ctxread=ctxread)
                comp_ast.append(a_ast)

            left = g.get_edges_for_node_filter(end_node=n, attr='e_type', val=EdgeType.LEFT)[1][0][0]

            left_ast = node_to_ast(left, g, var_def, ctxread=ctxread)

            ast_Comp = ast.Compare(left=left_ast, comparators=comp_ast, ops=g.get(n, 'ops'), lineno=0, col_offset=0)

            return ast_Comp
        raise TypeError(f'Cannot convert {n},{na}')
    except:
        print(n)
        raise


def process_if_node(func_body, func_test):
    return ast.If(body=func_body, test=func_test, orelse=[], lineno=0, col_offset=0)


def process_assign_node(target_nodes, g, var_def, value_ast, na, targets):
    if len(target_nodes) > 1:
        target_ast = []
        for target_node in target_nodes:
            target_ast.append(node_to_ast(target_node[1], g, var_def, read=False))
            targets.append(target_node[1])
        ast_assign = ast.Assign(targets=[ast.Tuple(elts=target_ast, lineno=0, col_offset=0, ctx=ast.Store())],
                                value=value_ast, lineno=0, col_offset=0)
        return ast_assign
    else:
        target_node = target_nodes[0][1]
        target_ast = node_to_ast(target_node, g, var_def, read=False)
        if value_ast and target_ast:
            if na == ast.Assign or target_node not in targets:
                targets.append(target_node)
                ast_assign = ast.Assign(targets=[target_ast], value=value_ast, lineno=0, col_offset=0)
            else:
                ast_assign = ast.AugAssign(target=target_ast, value=value_ast, lineno=0, col_offset=0, op=ast.Add())
            return ast_assign


def generate_return_statement(var_def_, g):
    if (l := len(var_def_.get_targets())) > 1:
        return_ = ast.Return(value=ast.Tuple(elts=var_def_.get_order_trgs()))
    elif l == 1:
        return_ = ast.Return(value=var_def_.get_order_trgs()[0])
    else:
        g.as_graphviz('noret', force=True)
        raise IndexError(f'Function {g.lablel} should have return, no?')
    return return_


def function_from_graph_generic(g: MappingsGraph, var_def_, arg_metadata):
    decorators = []
    body = function_body_from_graph(g, var_def_)
    var_def_.order_variables(arg_metadata)
    body.append(generate_return_statement(var_def_, g))

    args = ast.arguments(posonlyargs=[], args=var_def_.get_order_args(), vararg=None, defaults=[], kwonlyargs=[],
                         kwarg=None)

    func = wrap_function(g.label, body, decorators=decorators, args=args)

    target_ids = []
    for i, arg in enumerate(var_def_.args_order):
        if arg in var_def_.targets:
            target_ids.append(i)
    return func, var_def_.args_order, target_ids


def compare_expresion_from_graph(g, var_def_, lineno_count=1):
    top_nodes = g.topological_nodes()
    var_def = var_def_.var_def
    body = []
    for n in top_nodes:
        lineno_count += 1
        if g.get(n, 'ast_type') == ast.Compare:
            body.append(node_to_ast(n, g, var_def, ctxread=True))
    return body


def function_body_from_graph(g, var_def_, lineno_count=1, level=0):
    g.topological_nodes(ignore_cyclic=True) # give warning if cyclic, but ignore sorting
    top_nodes = range(0,len(g.nodes))
    var_def = var_def_.var_def
    body = []
    targets = []
    for n in top_nodes:
        lineno_count += 1
        if (at := g.get(n, 'ast_type')) == ast.Assign or at == ast.AugAssign:
            value_node = g.get_edges_for_node_filter(end_node=n, attr='e_type', val=EdgeType.VALUE)[1][0][0]

            value_ast = node_to_ast(value_node, g, var_def, ctxread=True)
            body.append(process_assign_node(g.get_edges_for_node_filter(start_node=n, attr='e_type',
                                                                        val=EdgeType.TARGET)[1],
                                            g, var_def, value_ast, at, targets))
        if (g.get(n, 'ast_type')) == ast.If:
            func_body = function_body_from_graph(g.nodes[n].subgraph_body, var_def_,
                                                 lineno_count=lineno_count, level=level+1)
            func_test = compare_expresion_from_graph(g.nodes[n].subgraph_test, var_def_,
                                                     lineno_count=lineno_count)
            body.append(process_if_node(func_body, func_test))
    return body


def compiled_function_from_graph_generic_llvm(g: Graph, var_def_, imports,
                                              compiled_function=False):
    func, signature, fname, r_args, r_targets = function_from_graph_generic_llvm(g, var_def_)
    if not compiled_function:
        return func, signature, r_args, r_targets

    body = []
    for (module, g.label) in imports.as_imports:
        body.append(ast.Import(names=[ast.alias(name=module, asname=g.label)], lineno=0, col_offset=0, level=0))
    for (module, g.label) in imports.from_imports:
        body.append(
            ast.ImportFrom(module=module, names=[ast.alias(name=g.label, asname=None)], lineno=0, col_offset=0,
                           level=0))
    body.append(func)
    body.append(ast.Return(value=ast.Name(id=fname, ctx=ast.Load(), lineno=0, col_offset=0), lineno=0, col_offset=0))

    func = wrap_function(fname + '1', body, decorators=[],
                         args=ast.arguments(posonlyargs=[], args=[], vararg=None, defaults=[],
                                            kwonlyargs=[], kw_defaults=[],lineno=0, kwarg=None))
    module_func = ast.Module(body=[func], type_ignores=[])
    code = compile(ast.parse(ast.unparse(module_func)), filename='llvm_equations_storage', mode='exec')
    namespace = {}
    exec(code, namespace)
    compiled_func = list(namespace.values())[1]()

    return compiled_func, signature, r_args, r_targets


def function_from_graph_generic_llvm(g: Graph, var_def_):
    fname = g.label + '_llvm'
    body = function_body_from_graph(g, var_def_)
    var_def_.order_variables(g.arg_metadata)
    args = ast.arguments(posonlyargs=[], args=var_def_.get_order_args(), vararg=None, defaults=[],
                         kwonlyargs=[], kw_defaults=[], kwarg=None)
    signature = [f'void(']
    target_ids = []
    for i, arg in enumerate(var_def_.args_order):
        if arg in var_def_.targets:
            signature.append("CPointer(float64), ")
            target_ids.append(i)
        else:
            signature.append("float64, ")
    signature[-1] = signature[-1][:-2]
    signature.append(")")
    signature = ''.join(signature)
    decorators = []

    func = wrap_function(fname, body, decorators=decorators, args=args)
    return func, signature, fname, var_def_.args_order, target_ids
