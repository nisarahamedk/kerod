# Copyright 2015 The TensorFlow Authors and modified by Emilien Garreau.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
# pylint: disable=invalid-name
"""ResNet models for Keras."""

import os

import tensorflow as tf
from tensorflow.keras import backend, layers
from tensorflow.keras.applications import resnet_v2, resnet
from tensorflow.python.keras.applications.resnet import stack2, stack1
from tensorflow.python.keras.utils import data_utils, layer_utils

BASE_WEIGHTS_PATH = ('https://storage.googleapis.com/tensorflow/keras-applications/resnet/')
WEIGHTS_HASHES = {
    'resnet50': '4d473c1dd8becc155b73f8504c6f6626',
    'resnet101': '88cf7a10940856eca736dc7b7e228a21',
    'resnet152': 'ee4c566cf9a93f14d82f913c2dc6dd0c',
    'resnet50v2': 'fac2f116257151a9d068a22e544a4917',
    'resnet101v2': 'c0ed64b8031c3730f411d2eb4eea35b5',
    'resnet152v2': 'ed17cf2e0169df9d443503ef94b23b33',
}


def padd_for_aligning_pixels(inputs):
    """This padding operation is here to make the pixels of the output perfectly aligned,
    It padd with 0 the bottom and the right of the images
    """

    chan = inputs.shape[3]
    b4_stride = 32.0
    shape2d = tf.shape(inputs)[1:3]
    new_shape2d = tf.cast(
        tf.math.ceil(tf.cast(shape2d, tf.float32) / b4_stride) * b4_stride, tf.int32)
    pad_shape2d = new_shape2d - shape2d
    inputs = tf.pad(inputs,
                    tf.stack([[0, 0],
                              [0, pad_shape2d[0]],
                              [0, pad_shape2d[1]],
                              [0, 0]]),
                    name='conv1_pad') # yapf: disable
    inputs.set_shape([None, None, None, chan])
    return inputs


def ResNet(stack_fn,
           preact,
           use_bias,
           model_name='resnet',
           weights='imagenet',
           input_tensor=None,
           input_shape=None,
           preprocess_input=None,
           **kwargs):
    """Instantiates the ResNet, ResNetV2, and ResNeXt architecture.

    Optionally loads weights pre-trained on ImageNet.
    Note that the data format convention used by the model is
    the one specified in your Keras config at `~/.keras/keras.json`.

    Caution: Be sure to properly pre-process your inputs to the application.
    Please see `applications.preprocess_input` for an example.
    
    Arguments:

    - *stack_fn*: a function that returns output tensor for the
        stacked residual blocks.
    - *preact*: whether to use pre-activation or not
        (True for ResNetV2, False for ResNet and ResNeXt).
    - *use_bias*: whether to use biases for convolutional layers or not
        (True for ResNet and ResNetV2, False for ResNeXt).
    - *model_name*: string, model name.
        include_top: whether to include the fully-connected
        layer at the top of the network.
    - *weights*: one of `None` (random initialization),
        'imagenet' (pre-training on ImageNet),
        or the path to the weights file to be loaded.
    - *input_tensor*: optional Keras tensor
        (i.e. output of `layers.Input()`)
        to use as image input for the model.
    - *input_shape*: optional shape tuple, only to be specified
        if `include_top` is False (otherwise the input shape
        has to be `(224, 224, 3)` (with `channels_last` data format)
        or `(3, 224, 224)` (with `channels_first` data format).
        It should have exactly 3 inputs channels.
    - *preprocess_input*: Preprocess input function

    Returns:
        A `keras.Model` instance.

    Raises:
        ValueError: in case of invalid argument for `weights`,
        or invalid input shape.
        ValueError: if `classifier_activation` is not `softmax` or `None` when
        using a pretrained top layer.
    """
    if kwargs:
        raise ValueError('Unknown argument(s): %s' % (kwargs,))
    if not (weights in {'imagenet', None} or os.path.exists(weights)):
        raise ValueError('The `weights` argument should be either '
                         '`None` (random initialization), `imagenet` '
                         '(pre-training on ImageNet), '
                         'or the path to the weights file to be loaded.')

    if input_tensor is None:
        img_input = layers.Input(shape=input_shape)
    else:
        if not backend.is_keras_tensor(input_tensor):
            img_input = layers.Input(tensor=input_tensor, shape=input_shape)
        else:
            img_input = input_tensor

    bn_axis = 3 if backend.image_data_format() == 'channels_last' else 1

    x = preprocess_input(img_input)
    x = layers.Lambda(padd_for_aligning_pixels, name="padd_for_aligning_pixels")(x)

    x = layers.Conv2D(64, 7, strides=2, use_bias=use_bias, name='conv1_conv')(x)

    if not preact:
        x = layers.BatchNormalization(axis=bn_axis, epsilon=1.001e-5, name='conv1_bn')(x)
        x = layers.Activation('relu', name='conv1_relu')(x)

    x = layers.ZeroPadding2D(padding=((1, 1), (1, 1)), name='pool1_pad')(x)
    x = layers.MaxPooling2D(3, strides=2, name='pool1_pool')(x)

    outputs = stack_fn(x)

    if preact:
        x = layers.BatchNormalization(axis=bn_axis, epsilon=1.001e-5, name='post_bn')(outputs[-1])
        x = layers.Activation('relu', name='post_relu')(x)
        outputs[-1] = x

    # Ensure that the model takes into account
    # any potential predecessors of `input_tensor`.
    if input_tensor is not None:
        inputs = layer_utils.get_source_inputs(input_tensor)
    else:
        inputs = img_input

    # Create model.
    model = tf.keras.Model(inputs, outputs, name=model_name)

    # Load weights.
    if (weights == 'imagenet') and (model_name in WEIGHTS_HASHES):
        file_name = model_name + '_weights_tf_dim_ordering_tf_kernels_notop.h5'
        file_hash = WEIGHTS_HASHES[model_name]
        weights_path = data_utils.get_file(file_name,
                                           BASE_WEIGHTS_PATH + file_name,
                                           cache_subdir='models',
                                           file_hash=file_hash)
        model.load_weights(weights_path)
    elif weights is not None:
        model.load_weights(weights)

    return model


def ResNet50V2(weights='imagenet', input_tensor=None, input_shape=None):

    def stack_fn(x):
        s2 = stack2(x, 64, 3, name='conv2')
        s3 = stack2(s2, 128, 4, name='conv3')
        s4 = stack2(s3, 256, 6, name='conv4')
        s5 = stack2(s4, 512, 3, stride1=1, name='conv5')
        return [s2, s3, s4, s5]

    return ResNet(stack_fn,
                  True,
                  True,
                  'resnet50v2',
                  weights,
                  input_tensor,
                  input_shape,
                  preprocess_input=resnet_v2.preprocess_input)


def ResNet101V2(
    weights='imagenet',
    input_tensor=None,
    input_shape=None,
):
    """Instantiates the ResNet101V2 architecture."""

    def stack_fn(x):
        s2 = stack2(x, 64, 3, name='conv2')
        s3 = stack2(s2, 128, 4, name='conv3')
        s4 = stack2(s3, 256, 23, name='conv4')
        s5 = stack2(s4, 512, 3, stride1=1, name='conv5')
        return [s2, s3, s4, s5]

    return ResNet(stack_fn,
                  True,
                  True,
                  'resnet101v2',
                  weights,
                  input_tensor,
                  input_shape,
                  preprocess_input=resnet_v2.preprocess_input)


def ResNet152V2(
    weights='imagenet',
    input_tensor=None,
    input_shape=None,
):
    """Instantiates the ResNet152V2 architecture."""

    def stack_fn(x):
        s2 = stack2(x, 64, 3, name='conv2')
        s3 = stack2(s2, 128, 8, name='conv3')
        s4 = stack2(s3, 256, 36, name='conv4')
        s5 = stack2(s4, 512, 3, stride1=1, name='conv5')
        return [s2, s3, s4, s5]

    return ResNet(stack_fn,
                  True,
                  True,
                  'resnet152v2',
                  weights,
                  input_tensor,
                  input_shape,
                  preprocess_input=resnet_v2.preprocess_input)


def ResNet50(include_top=True,
             weights='imagenet',
             input_tensor=None,
             input_shape=None,
             pooling=None,
             classes=1000,
             **kwargs):
    """Instantiates the ResNet50 architecture."""

    def stack_fn(x):
        x = stack1(x, 64, 3, stride1=1, name='conv2')
        x = stack1(x, 128, 4, name='conv3')
        x = stack1(x, 256, 6, name='conv4')
        return stack1(x, 512, 3, name='conv5')

    return ResNet(stack_fn,
                  False,
                  True,
                  'resnet50',
                  weights,
                  input_tensor,
                  input_shape,
                  preprocess_input=resnet.preprocess_input,
                  **kwargs)


def ResNet101(include_top=True,
              weights='imagenet',
              input_tensor=None,
              input_shape=None,
              pooling=None,
              classes=1000,
              **kwargs):
    """Instantiates the ResNet101 architecture."""

    def stack_fn(x):
        x = stack1(x, 64, 3, stride1=1, name='conv2')
        x = stack1(x, 128, 4, name='conv3')
        x = stack1(x, 256, 23, name='conv4')
        return stack1(x, 512, 3, name='conv5')

    return ResNet(stack_fn,
                  False,
                  True,
                  'resnet101',
                  weights,
                  input_tensor,
                  input_shape,
                  preprocess_input=resnet.preprocess_input,
                  **kwargs)


def ResNet152(include_top=True,
              weights='imagenet',
              input_tensor=None,
              input_shape=None,
              pooling=None,
              classes=1000,
              **kwargs):
    """Instantiates the ResNet152 architecture."""

    def stack_fn(x):
        x = stack1(x, 64, 3, stride1=1, name='conv2')
        x = stack1(x, 128, 8, name='conv3')
        x = stack1(x, 256, 36, name='conv4')
        return stack1(x, 512, 3, name='conv5')

    return ResNet(stack_fn,
                  False,
                  True,
                  'resnet152',
                  weights,
                  input_tensor,
                  input_shape,
                  preprocess_input=resnet.preprocess_input,
                  **kwargs)
