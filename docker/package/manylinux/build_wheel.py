import os
import subprocess
import tempfile
from pathlib import Path


def build_arg_env(env_var_name):
    val = os.getenv(env_var_name)
    return f"--build-arg {env_var_name}={val}"


def build_img(cuda_version, oneflow_src_dir, use_tuna, use_system_proxy, skip_img):
    cudnn_version = 7
    if str(cuda_version).startswith("11"):
        cudnn_version = 8
    from_img = f"nvidia/cuda:{cuda_version}-cudnn{cudnn_version}-devel-centos7"
    img_tag = f"oneflow:manylinux2014-cuda{cuda_version}"
    if skip_img == False:
        tuna_build_arg = ""
        if use_tuna:
            tuna_build_arg = '--build-arg use_tuna_yum=1 --build-arg pip_args="-i https://pypi.tuna.tsinghua.edu.cn/simple"'
        proxy_build_args = []
        if use_system_proxy:
            for v in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
                proxy_build_args.append(build_arg_env(v))
        proxy_build_arg = " ".join(proxy_build_args)
        cmd = f"docker build -f docker/package/manylinux/Dockerfile {proxy_build_arg} {tuna_build_arg} --build-arg from={from_img} -t {img_tag} ."
        print(cmd)
        subprocess.check_call(cmd, cwd=oneflow_src_dir, shell=True)
    return img_tag


def common_cmake_args(cache_dir):
    third_party_install_dir = os.path.join(cache_dir, "build-third-party-install")
    return f"-DCMAKE_BUILD_TYPE=Release -DBUILD_RDMA=ON -DTHIRD_PARTY_DIR={third_party_install_dir}"


def get_build_dir_arg(cache_dir, oneflow_src_dir):
    build_dir_real = os.path.join(cache_dir, "build")
    build_dir_mount = os.path.join(oneflow_src_dir, "build")
    return f"-v {build_dir_real}:{build_dir_mount}"


def create_tmp_bash_and_run(docker_cmd, img, bash_cmd):
    with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8") as f:
        f.write(bash_cmd)
        f.flush()
        print(bash_cmd)
        docker_cmd = f"{docker_cmd} -v /tmp:/host/tmp {img}"
        f_name = "/host" + f.name
        cmd = f"{docker_cmd} bash {f_name}"
        print(cmd)
        subprocess.check_call(cmd, shell=True)


def get_common_docker_args(oneflow_src_dir=None, cache_dir=None, current_dir=None):
    root = Path(cache_dir)
    child = Path(current_dir)
    assert root in child.parents
    cwd = os.getcwd()
    pwd_arg = f"-v {cwd}:{cwd}"
    cache_dir_arg = f"-v {cache_dir}:{cache_dir}"
    build_dir_arg = get_build_dir_arg(cache_dir, oneflow_src_dir)
    return f"-v {oneflow_src_dir}:{oneflow_src_dir} {pwd_arg} {cache_dir_arg} {build_dir_arg} -w {current_dir}"


def build_third_party(img_tag, oneflow_src_dir, cache_dir, extra_oneflow_cmake_args):
    third_party_build_dir = os.path.join(cache_dir, "build-third-party")
    cmake_cmd = " ".join(
        [
            "cmake",
            common_cmake_args(cache_dir),
            "-DTHIRD_PARTY=ON, -DONEFLOW=OFF",
            extra_oneflow_cmake_args,
            oneflow_src_dir,
        ]
    )

    bash_cmd = f"""
set -ex
{cmake_cmd}
make -j`nproc` prepare_oneflow_third_party
"""
    common_docker_args = get_common_docker_args(
        oneflow_src_dir=oneflow_src_dir,
        cache_dir=cache_dir,
        current_dir=third_party_build_dir,
    )
    docker_cmd = f"docker run --rm -it {common_docker_args}"
    create_tmp_bash_and_run(docker_cmd, img_tag, bash_cmd)


def get_python_bin(version):
    assert version in ["3.5", "3.6", "3.7", "3.8"]
    py_ver = "".join(version.split("."))
    py_abi = f"cp{py_ver}-cp{py_ver}"
    if py_ver != "38":
        py_abi = f"{py_abi}m"
    py_root = f"/opt/python/{py_abi}"
    py_bin = f"{py_root}/bin/python"
    return py_bin


def build_oneflow(
    img_tag,
    oneflow_src_dir,
    cache_dir,
    extra_oneflow_cmake_args,
    python_version,
    skip_wheel,
):
    oneflow_build_dir = os.path.join(cache_dir, "build-oneflow")
    python_bin = get_python_bin(python_version)
    cmake_cmd = " ".join(
        [
            "cmake",
            common_cmake_args(cache_dir),
            "-DTHIRD_PARTY=OFF, -DONEFLOW=ON",
            extra_oneflow_cmake_args,
            "-DCMAKE_EXPORT_COMPILE_COMMANDS=1",
            f"-DPython3_EXECUTABLE={python_bin}",
            oneflow_src_dir,
        ]
    )
    common_docker_args = get_common_docker_args(
        oneflow_src_dir=oneflow_src_dir,
        cache_dir=cache_dir,
        current_dir=oneflow_build_dir,
    )
    docker_cmd = f"docker run --rm -it {common_docker_args}"
    bash_cmd = f"""
set -ex
{cmake_cmd}
cmake --build . -j `nproc`
make -j`nproc` prepare_oneflow_third_party
"""
    if skip_wheel == False:
        bash_cmd += """
rm -rf $ONEFLOW_BUILD_DIR/python_scripts/*.egg-info
$PY_BIN setup.py bdist_wheel -d tmp_wheel --build_dir $ONEFLOW_BUILD_DIR --package_name $PACKAGE_NAME
auditwheel repair tmp_wheel/*.whl --wheel-dir $HOUSE_DIR
"""
    create_tmp_bash_and_run(docker_cmd, img_tag, bash_cmd)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cache_dir", type=str, required=False, default=None,
    )
    parser.add_argument(
        "--wheel_house_dir", type=str, required=False, default="wheelhouse",
    )
    parser.add_argument(
        "--python_version", type=str, required=False, default="3.5, 3.6, 3.7, 3.8",
    )
    parser.add_argument(
        "--cuda_version", type=str, required=False, default="10.2",
    )
    parser.add_argument(
        "--extra_oneflow_cmake_args", type=str, required=False, default="",
    )
    parser.add_argument(
        "--oneflow_src_dir", type=str, required=False, default=os.getcwd(),
    )
    parser.add_argument(
        "--skip_third_party", default=False, action="store_true", required=False
    )
    parser.add_argument(
        "--skip_wheel", default=False, action="store_true", required=False
    )
    parser.add_argument(
        "--skip_img", default=False, action="store_true", required=False
    )
    parser.add_argument(
        "--use_tuna", default=False, action="store_true", required=False
    )
    parser.add_argument(
        "--use_system_proxy", default=False, action="store_true", required=False
    )
    parser.add_argument("--xla", default=False, action="store_true", required=False)
    parser.add_argument(
        "--aliyun_mirror", default=False, action="store_true", required=False
    )
    parser.add_argument("--cpu", default=False, action="store_true", required=False)
    args = parser.parse_args()
    img_tag = build_img(
        args.cuda_version,
        args.oneflow_src_dir,
        args.use_tuna,
        args.use_system_proxy,
        args.skip_img,
    )
    extra_oneflow_cmake_args = args.extra_oneflow_cmake_args

    cuda_versions = []
    if args.aliyun_mirror:
        extra_oneflow_cmake_args += " -DTHIRD_PARTY_MIRROR=aliyun"
    if args.cpu:
        extra_oneflow_cmake_args += " -DBUILD_CUDA=OFF"
        cuda_versions = ["10.2"]
    else:
        extra_oneflow_cmake_args += " -DBUILD_CUDA=ON"
    cuda_versions = args.cuda_version.split(",")
    if args.xla == True and args.cpu == True:
        raise ValueError("flag xla can't coexist with flag cpu")
    for cuda_version in cuda_versions:
        cuda_version = cuda_version.strip()
        cache_dir = None
        if args.cache_dir:
            cache_dir = args.cache_dir
        else:
            cache_dir = os.path.join(os.getcwd(), "manylinux2014-build-cache")
            sub_dir = cuda_version
            if args.xla:
                sub_dir += "-xla"
            if args.cpu:
                sub_dir = "cpu"
            cache_dir = os.path.join(cache_dir, sub_dir)
        build_third_party(
            img_tag, args.oneflow_src_dir, cache_dir, extra_oneflow_cmake_args
        )
