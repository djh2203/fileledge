document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    const fileInput = document.querySelector('input[type="file"]');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const statusDiv = document.getElementById('upload-status');

    if (!form) return;  // 如果页面上没有表单（比如在 files 页面），就不执行后续

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const file = fileInput.files[0];
        if (!file) {
            alert('请先选择一个文件');
            return;
        }
        if (file.size > MAX_FILE_SIZE) {
            alert('QWQ 文件过大，最大允许 ' + (MAX_FILE_SIZE / 1024 / 1024).toFixed(0) + ' MB~');
            return;  // 阻止上传
        }

        const formData = new FormData();
        formData.append('file', file);

        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = percent + '%';
                progressBar.textContent = percent + '%';
            }
        });

        xhr.addEventListener('load', function() {
            if (xhr.status === 200) {
                statusDiv.innerHTML = '<span style="color: green;">上传成功！</span>';
                setTimeout(() => {
                    location.reload();
                }, 1000);
                fileInput.value = '';
            } else {
                statusDiv.innerHTML = '<span style="color: red;">上传失败：' + xhr.responseText + '</span>';
            }
            setTimeout(() => {
                progressContainer.style.display = 'none';
                progressBar.style.width = '0%';
                progressBar.textContent = '0%';
                statusDiv.innerHTML = '';
            }, 3000);
        });

        xhr.addEventListener('error', function() {
            statusDiv.innerHTML = '<span style="color: red;">上传出错，请重试</span>';
        });

        xhr.open('POST', '/upload');
        progressContainer.style.display = 'block';
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
        statusDiv.innerHTML = '上传中...';
        xhr.send(formData);
    });
});