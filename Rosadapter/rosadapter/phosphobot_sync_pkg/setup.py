from setuptools import find_packages, setup

package_name = 'phosphobot_sync_pkg'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'requests', 'scipy'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='root@todo.todo',
    description='Phosphobot synchronization - sends commands to physical arm HTTP API',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'phosphobot_sync = phosphobot_sync_pkg.phosphobot_sync:main'
        ],
    },
)
