from collections import OrderedDict
import numpy as np
import oneflow as flow
from test_util import GenArgList
import oneflow.typing as oft

g_samples = [{'input': [[[86, 97, 82], [14, 45, 87], [86, 88, 37]], [[15, 90, 49], [47, 76, 75], [2, 15, 30]]], 'index': [[[1, 1, 1], [1, 1, 0]], [[1, 0, 0], [1, 1, 0]]], 'dim': 1, 'out': [[[14, 45, 87], [14, 45, 82]], [[47, 90, 49], [47, 76, 49]]]}, {'input': [[[84, 90, 12], [22, 17, 0], [64, 42, 10]], [[9, 61, 43], [36, 42, 49], [19, 86, 79]]], 'index': [[[0, 1, 1], [1, 1, 1]], [[1, 1, 0], [0, 1, 1]]], 'dim': 1, 'out': [[[84, 17, 0], [22, 17, 0]], [[36, 42, 43], [9, 42, 49]]]}, {'input': [[[28, 79, 31], [63, 64, 63], [17, 47, 16]], [[54, 4, 95], [29, 21, 21], [29, 33, 5]]], 'index': [[[1, 1, 1], [0, 0, 0]], [[0, 0, 1], [1, 1, 1]]], 'dim': 1, 'out': [[[63, 64, 63], [28, 79, 31]], [[54, 4, 21], [29, 21, 21]]]}]

def _make_gather_dim_fn(
    input, index, dim, device_type, mirrored
):
    flow.clear_default_session()
    func_config = flow.FunctionConfig()
    func_config.default_data_type(flow.int32)

    def do_gather(x_blob, i_blob):
        with flow.scope.placement(device_type, "0:0"):
            func_config.default_logical_view(flow.scope.consistent_view())
            x = flow.get_variable(
                "input",
                shape=input.shape,
                dtype=flow.int32,
                initializer=flow.constant_initializer(0),
            )
            x = flow.cast_to_current_logical_view(x)
            x = x + x_blob

            y = flow.gather_dim(x, dim, i_blob)
            # flow.optimizer.SGD(
            #     flow.optimizer.PiecewiseConstantScheduler([], [1e-3]), momentum=0
            # ).minimize(y)
        return y

    @flow.global_function(type="predict", function_config=func_config)
    def gather_fn(
        params_def: oft.Numpy.Placeholder(input.shape, dtype=flow.int32),
        indices_def: oft.Numpy.Placeholder(index.shape, dtype=flow.int32),
    ):
        return do_gather(params_def, indices_def)

    return gather_fn

def _compare_gatherdim_with_samples(
    test_case,
    device_type,
    input,
    index,
    out,
    dim,
    mirrored=False,
):
    params, indices = input, index

    gather_fn = _make_gather_dim_fn(
        params, indices, dim, device_type, mirrored
    )

    of_y = gather_fn(params, indices).get().numpy()

    test_case.assertTrue(np.array_equal(out, of_y))

def test_gather(test_case):
    global g_samples
    arg_dict = OrderedDict()
    arg_dict["device_type"] = ["gpu", "cpu"]
    for sample in g_samples:
        input = np.array(sample["input"]).astype(np.int32)
        index = np.array(sample["index"]).astype(np.int32)
        _compare_gatherdim_with_samples(test_case,
        "gpu",
        input,
        index,
        np.array(sample["out"]).astype(np.int32),
        sample["dim"])
