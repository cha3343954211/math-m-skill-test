clc
clear
close all
load("t2_1.mat");
load("t2_1_tezheng.mat");
left =  left(cell)

for left = left%[50]   %  50    62    95
    xu1 = [];
    for i = 1:209
        panduan = sum(tezheng{left,1} == tezheng{i,1}) >= 170;
        if panduan == 1
            xu1 = [xu1,i];
        end
    end
    xu1
%     if length(xu1) == 19
%         xu1
%     end
end


% xu = zeros(19,1);
% xu(1) = find(xu1 == 50);
% cell1 = cell(1,xu1);
% 
% % for i = 1:length(xu)-1 
% %     xu(i+1) = xiayige_hang(cell1,xu(i));
% % end
% 
% xiayige_hang(cell1,8)
% 
% I = anhangpingtu(cell,[50,55,66]);
% % I = anliepingtu(cell,xu);
% 
% 
% imwrite(I,'yuantu.png') 
% imshow('yuantu.png')    









