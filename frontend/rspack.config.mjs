import { defineConfig } from '@rspack/cli';
import { rspack } from '@rspack/core';
import ReactRefreshPlugin from '@rspack/plugin-react-refresh';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const isDev = process.env.NODE_ENV === 'development';

export default defineConfig({
    entry: {
        main: './src/main.tsx',
    },
    output: {
        path: resolve(__dirname, 'dist'),
        filename: '[name].[contenthash].js',
        publicPath: '/',
        clean: true,
    },
    resolve: {
        extensions: ['.ts', '.tsx', '.js', '.jsx', '.json'],
    },
    module: {
        rules: [
            {
                test: /\.tsx?$/,
                use: {
                    loader: 'builtin:swc-loader',
                    options: {
                        jsc: {
                            parser: {
                                syntax: 'typescript',
                                tsx: true,
                            },
                            transform: {
                                react: {
                                    runtime: 'automatic',
                                    development: isDev,
                                    refresh: isDev,
                                },
                            },
                        },
                    },
                },
                type: 'javascript/auto',
            },
            {
                test: /\.css$/,
                use: [
                    'style-loader',
                    'css-loader',
                    'postcss-loader',
                ],
            },
            {
                test: /\.(png|jpe?g|gif|svg|webp)$/i,
                type: 'asset/resource',
            },
        ],
    },
    plugins: [
        new rspack.HtmlRspackPlugin({
            template: './index.html',
        }),
        new rspack.DefinePlugin({
            'import.meta.env.VITE_API_BASE_URL': JSON.stringify(
                process.env.VITE_API_BASE_URL || 'http://localhost:8000'
            ),
            'import.meta.env.DEV': JSON.stringify(isDev),
            'import.meta.env.PROD': JSON.stringify(!isDev),
            'import.meta.env.MODE': JSON.stringify(process.env.NODE_ENV || 'development'),
        }),
        isDev && new ReactRefreshPlugin(),
    ].filter(Boolean),
    devServer: {
        port: 5174,
        hot: true,
        historyApiFallback: true,
        open: false,
    },

    optimization: {
        minimize: !isDev,
    },
});
