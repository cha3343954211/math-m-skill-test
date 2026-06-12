clc
clear
close all

load("t2_1.mat");

for i=1:length(cell)
    level=graythresh(cell{1,i});
    cell{1,i}=imbinarize(cell{1,i},level);  %图像二值化处理
end

for i = 1:209
    mat = cell2mat(cell(1,i));
    lis = zeros(180,1);
    for j = 1:180
        lis(j) = sum(mat(j,:)) == 72;
    end
    tezheng{i,1} = lis;
end





