clc,clear,close all

load("t1_1.mat")

tou = diyige_hangtou(cell);
xu = zeros(19,1);
xu(1) = tou;
for i = 1:length(cell)-1 
    xu(i+1) = xiayige_hang(cell,xu(i));
end

%根据求出的序列xu画图
for i=1:19
    I(:,[72*(i-1)+1:72*i])=cell{1,xu(i)};     %将图复原
end

imwrite(I,'yuantu.png') 
imshow('yuantu.png')    





